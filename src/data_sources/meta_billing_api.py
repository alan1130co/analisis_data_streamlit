"""
Cliente para COBROS reales de Meta Ads (facturado) vía `/act_{id}/activities`
— alternativa a subir el CSV de Facturación a mano. Hermano de
`meta_ads_api.py` (gasto REAL diario vía Insights): mismo patrón de
paralelismo/retry/seguridad, reutilizando sus helpers genéricos de HTTP
(`_build_session`, `_request_with_retry`, `_next_request`, `_sanitize`) en
vez de duplicarlos.

Hallazgos empíricos (`scripts/diagnostic_meta_billing.py`, 2026-10 — ver ahí
la investigación completa):
- `GET /act_{id}/transactions` NO existe como edge (falla igual en v26.0 y
  v19.0 con "(#100) Tried accessing nonexisting field") — no es un problema
  de permisos, `business_management` SÍ está concedido al token.
- `GET /{business_id}/business_invoices` responde OK pero con 0 facturas —
  este negocio no está en facturación mensual consolidada de Meta.
- `GET /act_{id}/activities` SÍ trae cobros reales: cada evento con
  `event_type == "ad_account_billing_charge"` tiene `extra_data` (string
  JSON) con `new_value` (monto en CENTAVOS), `currency` y `transaction_id`
  — este último coincide BYTE A BYTE con la columna "Identificador de la
  transacción" del CSV de Facturación.
- El parámetro `event_type` del request NO filtra server-side (probado
  empíricamente con 2 formatos distintos: string plano y lista JSON-
  encodeada — ambos devuelven igual los demás tipos de evento mezclados).
  El filtro se hace en cliente, ver `_extract_billing_charges`.
- Revisando ~6500 eventos reales de las 3 cuentas (2025-01-01 a 2026-10-06)
  NO aparece ningún evento de crédito/reembolso/cupón en `/activities` —
  solo existe `ad_account_billing_charge` del lado de cobros. El "Crédito
  publicitario" que aparece en el CSV de Facturación viene de otro lado
  (cupones aplicados a la cuenta, visibles en
  `/act_{id}?fields=funding_source_details`, NO en el log de actividad).
  Por eso este cliente solo trae `ad_account_billing_charge`, igual que la
  sección "Pago de Anuncios de Meta" del CSV (no la de "Crédito publicitario").
- `event_time` viene en UTC; el CSV de Facturación pone la fecha en zona
  LOCAL (`APP_TIMEZONE` = America/Bogota, confirmado cruzando una
  transacción real cuyo `event_time` UTC caía en otro mes que la fecha del
  CSV) — se convierte ANTES de agrupar por mes, o un cobro de madrugada UTC
  (noche en Bogotá) queda en el mes equivocado.

Esquema de salida: idéntico al de `meta_ads_api.fetch_meta_ad_spend` (y por
lo tanto a `ad_spend.prepare_ad_spend`) — mismas columnas Fecha/Divisa/
Importe/Año/Mes_num/Mes_Año, agregado por transacción individual (no por
día, a diferencia de Insights) — compatible sin cambios con
`combine_real_vs_billed_monthly` y con las 6 gráficas de "Marketing e
Inversión" que ya reciben `gasto_raw` crudo.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from src.analytics.ad_spend import DIVISA_COL, FECHA_COL, IMPORTE_COL, MESES_ES
from src.config.settings import APP_TIMEZONE, META_ACCESS_TOKEN
from src.data_sources.meta_ads_api import (
    DEFAULT_SINCE,
    GRAPH_BASE_URL,
    MAX_PARALLEL_WORKERS,
    MAX_RETRIES,
    META_ACCOUNTS,
    MetaAdsAPIError,
    _build_session,
    _next_request,
    _request_with_retry,
    _sanitize,
)

ACTIVITIES_PAGE_LIMIT = 100
BILLING_CHARGE_EVENT = "ad_account_billing_charge"
EXPECTED_CURRENCY = "USD"
DEFAULT_TIMEOUT = 30

_PREPARED_COLUMNS = [FECHA_COL, DIVISA_COL, IMPORTE_COL, "Año", "Mes_num", "Mes_Año"]


def _parse_extra_data(raw) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def _fetch_account_activities(
    token: str, account_id: str, since: str, until: str, timeout: int = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Pagina completo `/act_{id}/activities` — devuelve TODOS los eventos
    (no solo cobros, ver `_extract_billing_charges` para el filtro), igual
    patrón de paginación que `meta_ads_api._fetch_account_insights`."""
    session = _build_session(token)
    url = f"{GRAPH_BASE_URL}/act_{account_id}/activities"
    params = {
        "fields": "event_type,event_time,extra_data",
        "since": since,
        "until": until,
        "limit": ACTIVITIES_PAGE_LIMIT,
    }

    records: list[dict] = []
    next_url: str | None = url
    next_params: dict | None = params

    while next_url is not None or next_params is not None:
        request_url = next_url if next_url is not None else url
        payload = _request_with_retry(session, request_url, next_params, token, timeout=timeout, retries=MAX_RETRIES)
        records.extend(payload.get("data", []))
        next_url, next_params = _next_request(next_params, payload)
        if next_url is None and next_params is None:
            break

    return records


def _extract_billing_charges(records: list[dict], account_label: str, warnings: list[str]) -> list[dict]:
    """Filtro EN CLIENTE por `event_type == "ad_account_billing_charge"`
    (el parámetro `event_type` del request no filtra server-side, ver
    docstring del módulo). Valida moneda: un cobro que NO sea USD se
    descarta y se reporta en `warnings` en vez de mezclarse silenciosamente
    con el resto (evitar sumar montos de monedas distintas como si fueran
    comparables)."""
    charges: list[dict] = []
    for r in records:
        if r.get("event_type") != BILLING_CHARGE_EVENT:
            continue
        extra = _parse_extra_data(r.get("extra_data"))
        amount_cents = extra.get("new_value")
        currency = extra.get("currency")
        transaction_id = extra.get("transaction_id")
        event_time = r.get("event_time")
        if amount_cents is None or transaction_id is None or not event_time:
            continue
        if currency != EXPECTED_CURRENCY:
            warnings.append(
                f"Meta Ads (facturado) — cuenta '{account_label}': cobro en moneda '{currency}' "
                f"(se esperaba {EXPECTED_CURRENCY}), transacción {transaction_id} IGNORADA para no "
                f"mezclar monedas distintas en el total."
            )
            continue
        charges.append({
            "event_time": event_time,
            "amount": amount_cents / 100.0,
            "transaction_id": transaction_id,
        })
    return charges


def _build_billed_dataframe(charges: list[dict]) -> pd.DataFrame:
    """Deduplica por `transaction_id` (globalmente, entre las 3 cuentas —
    aunque en la práctica cada transacción pertenece a una sola cuenta),
    convierte `event_time` de UTC a `APP_TIMEZONE` ANTES de derivar Año/
    Mes_num/Mes_Año (ver docstring del módulo), y arma el esquema idéntico
    al de `meta_ads_api.fetch_meta_ad_spend`/`ad_spend.prepare_ad_spend`."""
    if not charges:
        return pd.DataFrame(columns=_PREPARED_COLUMNS)

    df = pd.DataFrame(charges).drop_duplicates(subset=["transaction_id"])

    local = pd.to_datetime(df["event_time"], utc=True).dt.tz_convert(APP_TIMEZONE).dt.tz_localize(None)
    out = pd.DataFrame({
        FECHA_COL: local,
        DIVISA_COL: EXPECTED_CURRENCY,
        IMPORTE_COL: df["amount"].astype(float),
    })
    out["Año"] = out[FECHA_COL].dt.year
    out["Mes_num"] = out[FECHA_COL].dt.month
    out["Mes_Año"] = out["Mes_num"].map(MESES_ES) + " " + out["Año"].astype(str)
    out = out.sort_values(FECHA_COL).reset_index(drop=True)
    return out[_PREPARED_COLUMNS]


def fetch_meta_billed_amount(
    token: str = META_ACCESS_TOKEN,
    since: str = DEFAULT_SINCE,
    until: str | None = None,
    accounts: list[tuple[str, str]] | None = None,
    max_workers: int = MAX_PARALLEL_WORKERS,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[pd.DataFrame, list[str]]:
    """Trae lo FACTURADO (cobros reales) de Meta Ads vía `/activities` de
    las cuentas configuradas, en PARALELO (una cuenta por worker).

    Devuelve `(df, warnings)`:
      - `df`: mismo esquema que `meta_ads_api.fetch_meta_ad_spend` — una
        fila por transacción de cobro (no por día). Vacío (con las
        columnas esperadas) si todas las cuentas fallan o no hubo cobros
        en el rango, nunca lanza por una falla parcial.
      - `warnings`: una entrada por cuenta que falló (red/permiso/timeout)
        Y una entrada por cada cobro en una moneda distinta a USD
        (descartado, no mezclado) — todas sanitizadas, sin el token.
    """
    if not token:
        raise MetaAdsAPIError(
            "META_ACCESS_TOKEN no configurado. Definilo en .env, en "
            ".streamlit/secrets.toml, o pasalo al constructor/función."
        )

    if until is None:
        until = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d")
    accounts = accounts if accounts is not None else META_ACCOUNTS

    all_charges: list[dict] = []
    warnings: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_label = {
            executor.submit(_fetch_account_activities, token, account_id, since, until, timeout): label
            for label, account_id in accounts
        }
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                records = future.result()
                all_charges.extend(_extract_billing_charges(records, label, warnings))
            except Exception as exc:
                warnings.append(f"Meta Ads (facturado) — cuenta '{label}': {_sanitize(str(exc), token)}")

    df = _build_billed_dataframe(all_charges)
    return df, warnings


class MetaBillingAPIClient:
    """Cliente de alto nivel sobre `fetch_meta_billed_amount` — mismo rol
    que `meta_ads_api.MetaAdsAPIClient`, pero para lo FACTURADO (cobros)
    en vez del gasto real."""

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
        self.warnings: list[str] = []

    @property
    def source_name(self) -> str:
        return "API de Meta Ads (facturado)"

    def load(self) -> pd.DataFrame:
        df, warnings = fetch_meta_billed_amount(
            token=self.token, since=self.since, until=self.until,
            accounts=self.accounts, max_workers=self.max_workers, timeout=self.timeout,
        )
        self.warnings = warnings
        return df
