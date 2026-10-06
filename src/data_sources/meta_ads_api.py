"""
Cliente para la Meta Marketing API (Insights) — gasto REAL diario en pauta
publicitaria, sumado por día entre las 3 cuentas publicitarias configuradas
(SM CP Interna, Soluciones Migratorias, Contingencia).

Decisión clave (confirmada con el usuario, ver diagnóstico 2026-10-06 en
`scripts/diagnostic_meta_api.py`): se usa el endpoint de INSIGHTS
(`/act_<id>/insights`, `time_increment=1` = desglose diario), NO el de
`/transactions` (facturación) — Meta solo registra un cargo cuando el gasto
acumulado llega a un umbral (~$900 en estas cuentas), así que un gasto real
ya incurrido pero aún no facturado quedaría invisible si se usara
facturación como fuente. Insights da `spend` real día por día, sin ese hueco.

Versión de API: `v26.0` — confirmada por búsqueda web (2026-10-06) como la
más reciente estable (lanzada 2026-07-29); `v21.0` del diagnóstico original
ya expiró.

SEGURIDAD DEL TOKEN (crítico, ver auditoría de la tarea):
- El token se envía por header `Authorization: Bearer <token>`, NUNCA como
  parámetro de query string — a diferencia de `scripts/diagnostic_meta_api.py`
  (diagnóstico de un solo uso, ya ejecutado, no se retocó) que sí lo mandaba
  como `access_token` en los params. Con el token fuera de la URL, tampoco
  puede quedar embebido en `paging.next` (Graph API solo repite ahí los
  parámetros de query que se le mandaron, nunca los headers).
- Toda excepción de red/HTTP que pueda incluir la URL de la request (p.ej.
  `requests.exceptions.HTTPError`) pasa por `_sanitize()` antes de
  propagarse — reemplaza cualquier aparición literal del token por `***`.
  Defensa en profundidad: aunque el token ya no debería poder aparecer en
  una URL (headers no se reflejan ahí), se sanitiza de todos modos por si
  algún día cambia la forma de autenticar.
- Nunca se loguea el token ni se lo escribe a disco desde este módulo.

Esquema de salida: idéntico al que produce `ad_spend.prepare_ad_spend()`
sobre un CSV de Facturación (columnas `Fecha`/`Divisa`/`Importe`/`Año`/
`Mes_num`/`Mes_Año`, `Fecha` datetime64, `Importe` float64) — agregado por
DÍA sumando las 3 cuentas. Esto es intencional: al ser el mismo esquema que
ya consume `prepare_ad_spend` (idempotente sobre su propia salida — vuelve a
parsear "Fecha", reconfirma "Divisa"=="USD" y recalcula Año/Mes_num/Mes_Año
sin cambiar nada), el DataFrame de este cliente puede pasar DIRECTO a las 6
gráficas de "Marketing e Inversión" que ya reciben `gasto_raw` crudo del CSV
(`ad_spend_vs_closures.py`, `ad_spend_cost_per_lead.py`, etc.) sin tocar ni
una línea de esos 6 archivos.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from src.analytics.ad_spend import DIVISA_COL, FECHA_COL, IMPORTE_COL, MESES_ES
from src.config.settings import (
    APP_TIMEZONE,
    META_ACCESS_TOKEN,
    META_AD_ACCOUNT_ID_CONTINGENCIA,
    META_AD_ACCOUNT_ID_SM_CP_INTERNA,
    META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS,
)

META_API_VERSION = "v26.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"

# Rango por defecto: desde el inicio del histórico de pauta del negocio hasta
# hoy — configurable vía los parámetros `since`/`until` de `fetch_meta_ad_spend`.
DEFAULT_SINCE = "2025-01-01"

META_ACCOUNTS: list[tuple[str, str]] = [
    ("SM CP Interna", META_AD_ACCOUNT_ID_SM_CP_INTERNA),
    ("Soluciones Migratorias", META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS),
    ("Contingencia", META_AD_ACCOUNT_ID_CONTINGENCIA),
]

MAX_RETRIES = 3  # backoff 1s, 2s entre intentos — igual que clientify_api.py
MAX_PARALLEL_WORKERS = 3  # una cuenta por worker, las 3 en paralelo
DEFAULT_TIMEOUT = 30
PAGE_LIMIT = 500

_PREPARED_COLUMNS = [FECHA_COL, DIVISA_COL, IMPORTE_COL, "Año", "Mes_num", "Mes_Año"]


class MetaAdsAPIError(RuntimeError):
    """Error accionable — el mensaje SIEMPRE llega ya sanitizado (sin token)."""


def _sanitize(message: str, token: str) -> str:
    """Reemplaza cualquier aparición literal del token por `***`. Se aplica
    en todos los puntos donde una excepción de `requests` podría (en teoría)
    traer la URL completa de la request en su mensaje — defensa en
    profundidad, ver docstring del módulo."""
    text = str(message) if message is not None else ""
    if token:
        text = text.replace(token, "***")
    return text


def _build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _parse_spend(value) -> float:
    """Convierte el `spend` de Meta a float. El Graph API siempre devuelve
    un string con PUNTO decimal (ej. "123.45", confirmado empíricamente en
    el diagnóstico) — nunca coma europea de miles/decimales. Deliberadamente
    NO reutiliza `ad_spend._clean_importe` (pensada para el formato europeo
    del CSV de Facturación): ese heurístico asume que una coma presente es
    siempre decimal, y corrompería un eventual separador de miles estilo US
    (ej. "1,234.56" -> 1.23456 con esa lógica, en vez de 1234.56)."""
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _next_request(params: dict | None, payload: dict) -> tuple[str | None, dict | None]:
    """Decide la siguiente página a pedir, soportando las 2 formas en que
    Graph API puede exponer paginación: `paging.next` (URL completa, ya
    trae todos los parámetros codificados — no asumir que params=None es un
    bug, es justamente ese caso) o, si no viniera, `paging.cursors.after`
    (hay que reconstruir los params a mano agregando `after`). Devuelve
    `(None, None)` cuando no hay más páginas."""
    paging = payload.get("paging") or {}
    next_url = paging.get("next")
    if next_url:
        return next_url, None

    after = (paging.get("cursors") or {}).get("after")
    if after and params is not None:
        new_params = dict(params)
        new_params["after"] = after
        return None, new_params  # señal especial: reusar la URL base con estos params

    return None, None


def _request_with_retry(
    session: requests.Session, url: str, params: dict | None, token: str,
    timeout: int = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES,
) -> dict:
    """GET con reintentos (backoff 1s, 2s) ante cualquier error de red/HTTP.
    Todo lo que se propaga ya pasó por `_sanitize()` — nunca una excepción
    cruda de `requests` que pudiera (en teoría) llevar el token."""
    last_exc: MetaAdsAPIError | None = None
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            msg = str(exc)
            try:
                body = exc.response.json()
                msg = (body.get("error") or {}).get("message", msg)
            except Exception:
                pass
            last_exc = MetaAdsAPIError(_sanitize(msg, token))
        except requests.exceptions.RequestException as exc:
            last_exc = MetaAdsAPIError(_sanitize(str(exc), token))
        if attempt < retries - 1:
            time.sleep(2 ** attempt)  # 1s, luego 2s
    raise last_exc


def _fetch_account_insights(
    token: str, account_id: str, since: str, until: str, timeout: int = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Trae TODOS los registros diarios (`spend`/`date_start`/`date_stop`)
    de una cuenta, paginando completo — nunca asume que todo entra en una
    sola página."""
    session = _build_session(token)
    url = f"{GRAPH_BASE_URL}/act_{account_id}/insights"
    params = {
        "fields": "spend,date_start,date_stop",
        "time_increment": 1,
        "level": "account",
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": PAGE_LIMIT,
    }

    records: list[dict] = []
    next_url: str | None = url
    next_params: dict | None = params

    while next_url is not None or next_params is not None:
        request_url = next_url if next_url is not None else url
        payload = _request_with_retry(session, request_url, next_params, token, timeout=timeout)
        records.extend(payload.get("data", []))
        next_url, next_params = _next_request(next_params, payload)
        if next_url is None and next_params is None:
            break

    return records


def _account_records_to_df(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["date_start", "spend"])
    return pd.DataFrame({
        "date_start": [r.get("date_start") for r in records],
        "spend": [_parse_spend(r.get("spend")) for r in records],
    })


def _build_daily_dataframe(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Suma el `spend` de las 3 cuentas por día y arma el esquema final
    (idéntico al de `ad_spend.prepare_ad_spend` — ver docstring del módulo)."""
    non_empty = [f for f in frames if f is not None and not f.empty]
    if not non_empty:
        return pd.DataFrame(columns=_PREPARED_COLUMNS)

    combined = pd.concat(non_empty, ignore_index=True)
    daily = combined.groupby("date_start", as_index=False)["spend"].sum()

    out = pd.DataFrame({
        FECHA_COL: pd.to_datetime(daily["date_start"], errors="coerce"),
        DIVISA_COL: "USD",
        IMPORTE_COL: daily["spend"].astype(float),
    })
    out = out.dropna(subset=[FECHA_COL])
    if out.empty:
        return pd.DataFrame(columns=_PREPARED_COLUMNS)

    out["Año"] = out[FECHA_COL].dt.year
    out["Mes_num"] = out[FECHA_COL].dt.month
    out["Mes_Año"] = out["Mes_num"].map(MESES_ES) + " " + out["Año"].astype(str)
    out = out.sort_values(FECHA_COL).reset_index(drop=True)
    return out[_PREPARED_COLUMNS]


def fetch_meta_ad_spend(
    token: str = META_ACCESS_TOKEN,
    since: str = DEFAULT_SINCE,
    until: str | None = None,
    accounts: list[tuple[str, str]] | None = None,
    max_workers: int = MAX_PARALLEL_WORKERS,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[pd.DataFrame, list[str]]:
    """Trae el gasto real diario de Meta Ads (Insights) de las cuentas
    configuradas, en PARALELO (una cuenta por worker), y lo agrega por día
    sumando cuentas.

    Devuelve `(df, warnings)`:
      - `df`: mismo esquema que `ad_spend.prepare_ad_spend` — ver docstring
        del módulo. Si TODAS las cuentas fallan, `df` queda vacío (con las
        columnas esperadas) en vez de lanzar una excepción: el fallo real
        vive en `warnings`, para que la UI decida cómo mostrarlo.
      - `warnings`: una entrada de texto (sanitizada, SIN el token) por cada
        cuenta que falló (permiso, red, timeout, etc.) — una cuenta caída
        NUNCA tumba a las demás.
    """
    if not token:
        raise MetaAdsAPIError(
            "META_ACCESS_TOKEN no configurado. Definilo en .env, en "
            ".streamlit/secrets.toml, o pasalo al constructor/función."
        )

    if until is None:
        until = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d")
    accounts = accounts if accounts is not None else META_ACCOUNTS

    frames: list[pd.DataFrame] = []
    warnings: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_label = {
            executor.submit(_fetch_account_insights, token, account_id, since, until, timeout): label
            for label, account_id in accounts
        }
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                records = future.result()
                frames.append(_account_records_to_df(records))
            except Exception as exc:
                warnings.append(f"Meta Ads — cuenta '{label}': {_sanitize(str(exc), token)}")

    df = _build_daily_dataframe(frames)
    return df, warnings


class MetaAdsAPIClient:
    """Cliente de alto nivel sobre `fetch_meta_ad_spend` — mismo rol que
    `ClientifyAPIClient` para contactos, pero para gasto en pauta de Meta
    Ads. No hereda `ContactsDataSource` (ese contrato es específico de
    contactos de Clientify, con un esquema de columnas distinto); acá el
    contrato relevante es "misma forma que `prepare_ad_spend`".
    """

    def __init__(
        self,
        token: str = META_ACCESS_TOKEN,
        accounts: list[tuple[str, str]] | None = None,
        since: str = DEFAULT_SINCE,
        until: str | None = None,
        max_workers: int = MAX_PARALLEL_WORKERS,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not token:
            raise MetaAdsAPIError(
                "META_ACCESS_TOKEN no configurado. Definilo en .env, en "
                ".streamlit/secrets.toml, o pasalo al constructor."
            )
        self.token = token
        self.accounts = accounts if accounts is not None else META_ACCOUNTS
        self.since = since
        self.until = until
        self.max_workers = max_workers
        self.timeout = timeout
        # Se completa recién después de `load()` — lista vacía hasta entonces.
        self.warnings: list[str] = []

    @property
    def source_name(self) -> str:
        return "API de Meta Ads"

    def load(self) -> pd.DataFrame:
        """Trae y agrega el gasto real diario de las 3 cuentas. Las
        advertencias de cuentas fallidas quedan en `self.warnings` (lista,
        posiblemente vacía) para que el llamador decida cómo mostrarlas —
        esta función NUNCA lanza por una falla parcial, solo si TODO falla
        de una forma que impida construir el DataFrame (lo cual hoy no
        ocurre: `fetch_meta_ad_spend` siempre devuelve un DataFrame, vacío
        en el peor caso)."""
        df, warnings = fetch_meta_ad_spend(
            token=self.token, since=self.since, until=self.until,
            accounts=self.accounts, max_workers=self.max_workers, timeout=self.timeout,
        )
        self.warnings = warnings
        return df
