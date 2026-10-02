"""
Cliente para la API de Clientify.

Autenticación CONFIRMADA empíricamente (scripts/diagnostic_api_auth_formats.py,
contra GET /v1/contacts/ con un token real): el formato correcto es
`Authorization: Token <token>` — NO `Bearer`. `Bearer`/`Api-Token`/`X-Api-Key`/
`?token=` devuelven 404 "Api key not provided" (mecanismo ni reconocido);
`Authorization: Token` y `?api_key=` devuelven 401 con un token inválido y
200 con uno válido. Se eligió el header sobre el query param por ser el
método más estándar y no dejar el token en logs de acceso/URLs.

Mapeo de campos (confirmado contra datos reales, scripts/diagnostic_api_schema.py):
custom fields vienen INLINE en cada contacto (lista `custom_fields`, sin
endpoint aparte); el módulo Deals de la cuenta solo tiene 7 registros vacíos
(3 de ejemplo + 4 sin contacto/valor) — no se usa, todos los datos de cierre
viven en `custom_fields` del contacto. Mapeo deliberadamente SIMPLE: sin
cascadas nuevas de canal ni redefinición de reglas de negocio existentes —
ver el comentario de `PLACEHOLDER_ESTADO` más abajo para la única decisión
pendiente.

Mapeo COMPLETO de las 30 columnas que usa `analytics/*.py` (auditoría de
columnas del proyecto + verificación empírica contra la API real, ambas
persistidas en `scratch/`: `api_sample_contactos.json` — 20 contactos de
muestra —, `api_custom_fields_catalog.json` — catálogo completo de 45 custom
fields — y `api_sector_crosscheck_contacts.json` — 5 contactos cruzados 1:1
contra el Excel para confirmar `contact_sector`). Las últimas 9 columnas
mapeadas (demografía/ubicación/atribución) NO estaban en el mapeo original:
- `cumpleaños` ← `birthday` (campo nativo raíz, string "YYYY-MM-DD"). Poblado
  en 75% de la muestra — el resto queda NaN, no es un bug.
- `nombre` ← `first_name` + " " + `last_name` (ambos nativos; el Excel no
  separa nombre/apellido en 2 columnas, así que se concatenan acá).
- `ciudad 1`/`provincia/estado 1`/`país` ← `addresses[0].city`/`.state`/
  `.country`. El array `addresses` nunca trajo más de 1 elemento en la
  muestra (soporta que el Excel solo tenga "ciudad 1", no "ciudad 2").
  Poblado 35%/35%/55% respectivamente en la muestra — hueco de dato real de
  Clientify, no algo a "arreglar" acá.
- `sector` ← `contact_sector` (campo nativo raíz, NO un custom field —
  confirmado cruzando 5 contactos reales del Excel 1:1 contra su JSON de la
  API, ver `api_sector_crosscheck_contacts.json`; por eso no aparecía en el
  catálogo de 45 custom fields).
- `Tipo de proceso` / `Campaña - pauta` / `Publicacion por la que se
  contacto el cliente` ← custom fields con esos nombres EXACTOS (ids 418882,
  523562 y 444193 respectivamente en el catálogo real), mismo mecanismo de
  extracción que los custom fields ya mapeados.

Cache en disco (octubre 2026, ver `CONTACTS_CACHE_PATH`): persiste el
DataFrame normalizado entre reinicios de la app (a diferencia de
`@st.cache_data`, que es solo en memoria del proceso) y se fusiona por
`_contact_id` (`_upsert_contacts_df`) contra lo último que trajo la API, en
vez de reemplazarse a ciegas.

AUDITORÍA DE PERFORMANCE (octubre 2026): el plan original era además un
sync INCREMENTAL de verdad, pidiendo a `/contacts/` solo los contactos
modificados desde el último sync exitoso (`?modified__gte=`, rama separada
`_fetch_contacts_since` + `SYNC_STATE_PATH`/`last_synced_at` para recordar
cuándo fue ese último sync). Confirmado empíricamente que esta cuenta
IGNORA ese filtro (y 10 variantes de nombre más) en silencio — siempre
devuelve el dataset completo, filtro o no. Esa rama "incremental" quedó
ACTIVA igual después del primer sync exitoso pese a no cumplir su objetivo,
y además de no ahorrar contactos era SECUENCIAL (un `while` siguiendo
`next` página por página, sin los `MAX_PARALLEL_WORKERS` workers en
paralelo) — por lo que cada sync posterior al primero (incluido cada click
en "Actualizar datos") tardaba muchos minutos más que el sync inicial, sin
ningún beneficio a cambio. Eliminada por completo: con esta cuenta, TODO
sync (primero o posterior) usa siempre `_fetch_all_contacts` (paralelo).
Si el filtro empieza a funcionar del lado del servidor en el futuro, un
sync incremental real tendría que reconstruirse desde cero de todos modos
(un `while`/`next` secuencial nunca hubiera sido la forma correcta de
aprovecharlo).
"""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import streamlit as st

from .base import ContactsDataSource, normalize_contacts_df
from src.config.settings import APP_TIMEZONE, CACHE_DIR, CLIENTIFY_API_TOKEN, CLIENTIFY_BASE_URL
from src.utils.sync_timing import log_marker, timed_stage

# --- Custom fields que se copian tal cual (nombre EXACTO confirmado contra
# el catálogo real de la cuenta, GET /v1/custom-fields/ — 45 campos, estos
# 18 son los únicos que hoy consume analytics/). ---
NUMERIC_CUSTOM_FIELDS = [
    "Cantidad de cierres",
    "Valor total del proceso",
    "Valor total segundo cierre",
    "Valor total tercer cierre",
    "Valor total 4to cierre",
    "Cuota inicial pactada",
    "Cuota inicial segundo cierre",
    "Cuota inicial tercer cierre",
    "Cuota inicial 4to cierre",
]

DATE_CUSTOM_FIELDS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]

TEXT_CUSTOM_FIELDS = [
    "Origen de la pauta",
    "Motivo de no cierre",
    "Tipo de proceso",
    "Campaña - pauta",
    "Publicacion por la que se contacto el cliente",
]

CUSTOM_FIELD_NAMES = NUMERIC_CUSTOM_FIELDS + DATE_CUSTOM_FIELDS + TEXT_CUSTOM_FIELDS

# "canal online": la API usa "social-paid", el Excel (y `settings.PAID_NETWORK_
# CHANNELS`/is_marketing()/_is_paid_network() en metrics.py) esperan el string
# EXACTO "paid social" — sin este remapeo de VALOR, todo lead de redes pagas
# de la API caería silenciosamente fuera de Pauta.
MEDIUM_VALUE_MAP = {"social-paid": "paid social"}

# "estado": DECISIÓN TEMPORAL, pendiente de definir con el negocio (ver
# memoria del proyecto, entrada 2026-09-30). La API no tiene un campo
# confirmado equivalente al "activo"/"activo - mora"/"inactivo" del Excel
# (ese concepto es "¿el contrato sigue vigente/pagando?", no una etapa de
# embudo — el campo nativo "status" de la API es justamente una etapa de
# embudo: cold-lead/hot-lead/client/lost-client/in-deal/other, un concepto
# distinto). Se fija un valor fijo que NUNCA es "inactivo"
# (settings.CIERRE_INVALID_ESTADOS), para que `_is_valid_closure_estado()`
# considere válidos todos los cierres de origen API hasta que el negocio
# defina si existe un campo real para esto. Este valor NO representa nada
# real de Clientify — no usarlo para ninguna otra lógica.
PLACEHOLDER_ESTADO = "sin definir (api)"

CACHE_TTL_SECONDS = 900  # 15 minutos — ver justificación en el chat/PR.

# --- Cache en disco (sobrevive a reinicios de la app, a diferencia de
# @st.cache_data que es solo en memoria del proceso) ---
CONTACTS_CACHE_PATH = CACHE_DIR / "clientify_contacts_cache.parquet"

PAGE_SIZE = 250  # techo real confirmado empíricamente (ver _fetch_all_contacts)

# Concurrencia de `_fetch_all_contacts` — CONFIRMADA EMPÍRICAMENTE (octubre
# 2026) contra la cuenta real: 2 tandas de 10 requests simultáneas a páginas
# distintas (page_size=250 cada una) devolvieron 200 en las 20, con latencia
# por request IDÉNTICA a la de una request secuencial sola (~8-14s) — es
# decir, 10 páginas en paralelo tardaron lo mismo que 1 página sola, sin
# ningún 429, sin headers de rate-limit en la respuesta (`X-RateLimit-*`/
# `Retry-After` ausentes en ambas tandas). No se detectó degradación ni señal
# de techo real por debajo de 10 — se usa ese valor (el tope sugerido) en vez
# de seguir subiendo sin un motivo concreto para necesitar más.
MAX_PARALLEL_WORKERS = 10


def _build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    })
    return session


def _fetch_page(
    session: requests.Session, base_url: str, page: int, page_size: int = PAGE_SIZE, retries: int = 3
) -> dict:
    """Trae UNA página puntual vía `?page=N` (confirmado empíricamente que
    esta cuenta lo acepta directo — el propio campo `next` que devuelve la
    API tiene exactamente esta forma: `.../contacts/?page=2&page_size=250`,
    no hace falta seguir el link, alcanza con mandar el número).

    Reintenta hasta `retries` veces con backoff simple (1s, 2s) ante
    cualquier `RequestException` (timeout, conexión, HTTP 4xx/5xx vía
    `raise_for_status`) — así una página puntual que falla por un blip de
    red no tumba el sync completo por sí sola. Si se agotan los reintentos,
    propaga la excepción (no hay forma segura de "seguir sin esa página":
    silenciarlo dejaría un hueco de datos sin avisar a nadie).
    """
    url = f"{base_url.rstrip('/')}/contacts/"
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(url, params={"page_size": page_size, "page": page}, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 1s, luego 2s
    raise last_exc


def _fetch_all_contacts(
    token: str, base_url: str, max_workers: int = MAX_PARALLEL_WORKERS
) -> list[dict]:
    """Pagina por TODOS los contactos y devuelve la lista cruda de dicts,
    sin transformar.

    `page_size` (no `limit`) es el parámetro que de verdad controla el
    tamaño de página en esta cuenta — confirmado empíricamente: `limit`
    se ignora en silencio (siempre devuelve 25 por página, el default del
    servidor), `page_size` sí funciona, con un techo real de 250 por página
    aunque se pida más (~140 páginas para ~34k contactos).

    PARALELIZADO (octubre 2026, ver `MAX_PARALLEL_WORKERS` para la evidencia
    empírica de que esta cuenta tolera 10 requests simultáneas sin 429 ni
    degradación): se pide la página 1 sola primero (para conocer `count` real
    y confirmar `page_size` efectivo), se calcula cuántas páginas faltan, y
    el resto se piden en paralelo con `ThreadPoolExecutor`. Los resultados se
    acumulan en un dict indexado por número de página y se concatenan al
    final EN ORDEN (1, 2, 3, ...) — el resultado final es siempre el mismo
    sin importar en qué orden terminen de responder los workers.
    """
    session = _build_session(token)

    with timed_stage("Fetch API - página 1 (count)"):
        first_payload = _fetch_page(session, base_url, page=1)
    contacts: list[dict] = list(first_payload.get("results", []))
    count = first_payload.get("count", len(contacts))
    page_size = len(contacts) or PAGE_SIZE

    if count <= len(contacts):
        return contacts  # todo entraba en la página 1

    total_pages = math.ceil(count / page_size)
    remaining_pages = range(2, total_pages + 1)
    log_marker(
        f"Fetch API - páginas restantes: {len(remaining_pages)} páginas "
        f"({count} contactos totales), max_workers={max_workers}"
    )

    results_by_page: dict[int, list[dict]] = {}
    with timed_stage(f"Fetch API - bloque paralelo ({len(remaining_pages)} páginas)"):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {
                executor.submit(_fetch_page, session, base_url, page, page_size): page
                for page in remaining_pages
            }
            for future in as_completed(future_to_page):
                page = future_to_page[future]
                payload = future.result()  # si agotó reintentos, la excepción se propaga acá
                results_by_page[page] = payload.get("results", [])

    for page in remaining_pages:
        contacts.extend(results_by_page.get(page, []))

    return contacts


def _load_cached_contacts() -> pd.DataFrame | None:
    """Lee el cache en disco (`CONTACTS_CACHE_PATH`) si existe y es legible.

    `None` si el archivo no existe, está vacío, corrupto, o no tiene la
    forma esperada (índice `_contact_id`) — en cualquiera de esos casos el
    llamador debe caer a un full sync, nunca explotar.
    """
    if not CONTACTS_CACHE_PATH.exists():
        return None
    with timed_stage(f"Caché en disco - lectura .parquet ({CONTACTS_CACHE_PATH.name})"):
        try:
            df = pd.read_parquet(CONTACTS_CACHE_PATH)
        except Exception:
            return None
    if df.index.name != "_contact_id":
        return None
    log_marker(f"Caché en disco - leído: {len(df)} filas")
    return df


def _save_contacts_cache(df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with timed_stage(f"Caché en disco - escritura .parquet ({len(df)} filas)"):
        df.to_parquet(CONTACTS_CACHE_PATH)


def clear_disk_cache() -> None:
    """Borra el cache en disco (el .parquet de contactos), para forzar un
    full resync real en el próximo `load()`. No está conectada a ningún
    botón de la UI todavía (no se pidió para esta tarea) — queda disponible
    para quien quiera agregar un "Forzar sincronización completa" más
    adelante, o para limpiar manualmente si el cache quedara en un estado
    raro."""
    CONTACTS_CACHE_PATH.unlink(missing_ok=True)


def _upsert_contacts_df(cached_df: pd.DataFrame | None, new_df: pd.DataFrame) -> pd.DataFrame:
    """Fusiona `new_df` (recién traído, indexado por `_contact_id`) sobre
    `cached_df` (lo que había en disco): las filas de `new_df` reemplazan a
    las de `cached_df` con el mismo ID (contacto modificado), las que no
    existían se agregan (contacto nuevo). `cached_df=None`/vacío devuelve
    `new_df` tal cual (primera vez o cache corrupto).

    `new_df` siempre trae el dataset COMPLETO (todo sync usa
    `_fetch_all_contacts`, ver auditoría de performance en el docstring del
    módulo), así que en la práctica esto se comporta como un reemplazo
    total — el upsert por ID solo importa si Clientify alguna vez deja de
    devolver un contacto que sí estaba en disco (no se pierde). `keep="last"`
    es lo que hace que `new_df` gane sobre `cached_df` en caso de ID repetido.
    """
    if cached_df is None or cached_df.empty:
        return new_df
    combined = pd.concat([cached_df, new_df])
    return combined[~combined.index.duplicated(keep="last")]


def _to_nan_if_blank(value):
    """None o string vacío/blanco -> NaN. Necesario ANTES de pasar por
    `normalize_contacts_df`: su normalización de texto solo reconoce como
    "vacío" el string literal "nan" (el resultado de `str(float('nan'))`,
    que es como pandas representa una celda vacía de Excel) — un `None`
    crudo se convertiría en el string "none" y quedaría pegado como texto
    visible en vez de tratarse como faltante (rompería, por ejemplo,
    `df["propietario"].isna()` en funnel.py, usado para armar la fila "Sin
    asesor").
    """
    if value is None:
        return float("nan")
    if isinstance(value, str) and not value.strip():
        return float("nan")
    return value


def _full_name(contact: dict) -> object:
    """`nombre` ← `first_name` + " " + `last_name` (ambos campos nativos raíz).

    El Excel no separa nombre/apellido en 2 columnas (una sola "nombre"), así
    que se concatenan acá. `.strip()` evita un espacio colgante cuando
    `last_name` viene vacío (confirmado en la muestra real: `last_name` solo
    viene poblado en 90% de los contactos, `first_name` en 100%).
    """
    first = contact.get("first_name") or ""
    last = contact.get("last_name") or ""
    return _to_nan_if_blank(f"{first} {last}".strip())


def _first_address_value(contact: dict, field: str) -> object:
    """Extrae `addresses[0][field]` (city/state/country) para las columnas
    `ciudad 1`/`provincia/estado 1`/`país`.

    NaN (no string vacío) si `addresses` está ausente, es `None`, es una
    lista vacía, o el campo puntual viene en blanco — mismo criterio que
    `_to_nan_if_blank` en todo el resto de este archivo, para no reproducir
    el bug ya conocido de un valor vacío colándose como string y rompiendo
    `.isna()` aguas abajo. Confirmado contra una muestra real (ver
    `scratch/api_sample_contactos.json`) que el array nunca trae más de 1
    elemento y que city/state/country vienen poblados en 35%/35%/55% de los
    casos respectivamente — es un hueco de dato real de Clientify, no algo
    que este helper deba "arreglar".
    """
    addresses = contact.get("addresses") or []
    if not addresses or not isinstance(addresses[0], dict):
        return float("nan")
    return _to_nan_if_blank(addresses[0].get(field))


def _to_numeric_or_nan(value) -> float:
    """Castea un custom field Currency/Numeric a float, NaN si falta o no se
    puede parsear.

    Deliberadamente NO reutiliza `ad_spend._clean_importe`: esa función
    devuelve 0.0 para valores faltantes, correcto para gasto en pauta (una
    fila sin gasto cargado SÍ es $0), pero incorrecto acá — un contacto sin
    "Valor total del proceso" cargado debe quedar NaN (como una celda vacía
    de Excel), no convertirse en un cierre de $0.
    """
    if pd.isna(value):
        return float("nan")
    s = str(value).strip().replace(",", "")
    if not s:
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def _pivot_custom_fields(contacts: list[dict]) -> pd.DataFrame:
    """Convierte la lista `custom_fields` de cada contacto
    (`[{"field": "<nombre>", "value": "<valor>"}, ...]`) en columnas, una
    por cada nombre en CUSTOM_FIELD_NAMES. Un contacto sin un campo dado
    queda NaN en esa columna, igual que una celda vacía en el Excel.
    """
    rows = []
    for contact in contacts:
        row = {name: float("nan") for name in CUSTOM_FIELD_NAMES}
        for field in contact.get("custom_fields") or []:
            name = field.get("field")
            if name in row:
                row[name] = _to_nan_if_blank(field.get("value"))
        rows.append(row)
    return pd.DataFrame(rows, columns=CUSTOM_FIELD_NAMES)


def _build_dataframe(contacts: list[dict]) -> pd.DataFrame:
    """Arma el DataFrame crudo (pre-normalización) a partir de contactos de
    la API, con las mismas columnas que produce `ExcelContactsLoader` antes
    de llamar a `normalize_contacts_df`.
    """
    if not contacts:
        columns = [
            "creado", "propietario", "canal online", "Canal offline", "estado", "Etiquetas",
            "cumpleaños", "nombre", "ciudad 1", "provincia/estado 1", "país", "sector",
        ] + CUSTOM_FIELD_NAMES
        return pd.DataFrame(columns=columns)

    base_df = pd.DataFrame({
        "creado": [c.get("created") for c in contacts],
        "propietario": [_to_nan_if_blank(c.get("owner_name")) for c in contacts],
        "canal online": [
            MEDIUM_VALUE_MAP.get(c.get("medium") or "", c.get("medium")) for c in contacts
        ],
        "Canal offline": [_to_nan_if_blank((c.get("contact_source") or {}).get("name")) for c in contacts],
        # Etiquetas: en el Excel es un string único; en la API es una lista
        # de tags. Se unen con ", " para que las reglas existentes que hacen
        # df["Etiquetas"].str.contains("305-508-5147", ...) en metrics.py
        # sigan funcionando sin tocar analytics/ (ver justificación en el chat).
        "Etiquetas": [", ".join(c.get("tags") or []) for c in contacts],
        # "cumpleaños": no está en `base.DATE_COLS`, así que `normalize_contacts_df`
        # no la toca — igual que en el Excel, cada consumidor (closures_by_age.py)
        # la parsea con su propio `pd.to_datetime(..., dayfirst=True)`. El string
        # ISO "YYYY-MM-DD" de la API parsea igual de bien con ese flag que un
        # datetime ya nativo del Excel.
        "cumpleaños": [_to_nan_if_blank(c.get("birthday")) for c in contacts],
        "nombre": [_full_name(c) for c in contacts],
        "ciudad 1": [_first_address_value(c, "city") for c in contacts],
        "provincia/estado 1": [_first_address_value(c, "state") for c in contacts],
        "país": [_first_address_value(c, "country") for c in contacts],
        # "sector" ← `contact_sector`, campo NATIVO raíz (no un custom field —
        # confirmado cruzando 5 contactos reales contra el Excel, ver
        # scratch/api_sector_crosscheck_contacts.json). Valor libre, sin
        # transformación — igual que en el Excel, donde tampoco se normaliza
        # (no está en `base.TEXT_COLS`).
        "sector": [_to_nan_if_blank(c.get("contact_sector")) for c in contacts],
    })
    base_df["estado"] = PLACEHOLDER_ESTADO

    # "creado": ISO 8601 con offset (+02:00) -> naive en APP_TIMEZONE, para
    # quedar en el mismo formato (datetime naive, hora local) que produce
    # openpyxl al leer una fecha de Excel. Sin esto, mezclar esta columna
    # tz-aware con el resto del pipeline (tz-naive) rompe cualquier
    # comparación de fechas en filters.py/analytics/.
    creado_utc = pd.to_datetime(base_df["creado"], errors="coerce", utc=True)
    base_df["creado"] = creado_utc.dt.tz_convert(APP_TIMEZONE).dt.tz_localize(None)

    custom_df = _pivot_custom_fields(contacts)
    for col in NUMERIC_CUSTOM_FIELDS:
        custom_df[col] = custom_df[col].apply(_to_numeric_or_nan)
    # Las columnas de fecha (DATE_CUSTOM_FIELDS) y de texto (TEXT_CUSTOM_FIELDS)
    # se dejan tal cual (string "DD/MM/YYYY" o NaN) — `normalize_contacts_df`
    # las parsea/limpia exactamente igual que a las del Excel.

    return pd.concat([base_df.reset_index(drop=True), custom_df.reset_index(drop=True)], axis=1)


def _build_and_normalize_indexed(contacts: list[dict]) -> pd.DataFrame:
    """Igual que `_build_dataframe` + `normalize_contacts_df`, pero además
    indexa el resultado por `_contact_id` (el `id` nativo de cada contacto)
    para que `_upsert_contacts_df` pueda fusionar por identidad de contacto.

    Este índice es puramente un detalle interno del cache de disco — NUNCA
    llega a `analytics/`: `_fetch_and_build_dataframe` lo resetea a un
    RangeIndex normal antes de devolver el DataFrame (ver más abajo), así
    que no cambia nada del esquema/columnas que ya usa el resto del
    pipeline.
    """
    with timed_stage(f"_build_dataframe - mapeo de campos ({len(contacts)} contactos)"):
        raw_df = _build_dataframe(contacts)
    with timed_stage(f"normalize_contacts_df ({len(contacts)} contactos)"):
        df = normalize_contacts_df(raw_df)
    df.index = pd.Index([c.get("id") for c in contacts], name="_contact_id")
    return df


def _fetch_and_build_dataframe(token: str, base_url: str) -> pd.DataFrame:
    """Lógica real: pagina, mapea, normaliza, y fusiona contra el cache en
    disco (`CONTACTS_CACHE_PATH`) para sobrevivir a reinicios de la app. Sin
    `@st.cache_data` — así los tests la ejercitan directo, sin pelear con el
    cache global de Streamlit (ver `ClientifyAPIClient.load`, que sí cachea,
    para el uso en producción).

    Flujo: SIEMPRE full sync vía `_fetch_all_contacts` (paralelo, ver
    auditoría de performance en el docstring del módulo — la rama
    "incremental" que existía acá se eliminó por ser secuencial y no ahorrar
    tráfico). El resultado se fusiona por `_contact_id` sobre lo que ya
    había en disco (`_upsert_contacts_df`) y se persiste de nuevo.
    """
    log_marker("=== _fetch_and_build_dataframe: INICIO (inner st.cache_data MISS) ===")
    func_start = time.perf_counter()

    cached_df = _load_cached_contacts()
    contacts = _fetch_all_contacts(token, base_url)
    new_df = _build_and_normalize_indexed(contacts)

    with timed_stage(f"_upsert_contacts_df (merge contra {0 if cached_df is None else len(cached_df)} filas en disco)"):
        merged = _upsert_contacts_df(cached_df, new_df)

    _save_contacts_cache(merged)

    result = merged.reset_index(drop=True)
    log_marker(
        f"=== _fetch_and_build_dataframe: FIN — {len(result)} filas, "
        f"{time.perf_counter() - func_start:.2f} segundos totales ==="
    )
    return result


_cached_fetch_and_build_dataframe = st.cache_data(
    ttl=CACHE_TTL_SECONDS,
    show_spinner="Descargando contactos desde la API de Clientify...",
)(_fetch_and_build_dataframe)


def clear_cache() -> None:
    """Limpia el cache de `ClientifyAPIClient.load()` (botón "Actualizar
    datos" de la UI), para forzar una recarga inmediata desde la API en vez
    de esperar `CACHE_TTL_SECONDS`. Ver también `src/ui/api_source.py`, que
    tiene su propia capa de cache encima (`precompute_derived_columns`) y
    necesita limpiarse junto con esta.
    """
    _cached_fetch_and_build_dataframe.clear()


class ClientifyAPIClient(ContactsDataSource):
    """Cliente HTTP que carga contactos directamente desde la API de Clientify."""

    def __init__(self, token: str = CLIENTIFY_API_TOKEN, base_url: str = CLIENTIFY_BASE_URL):
        if not token:
            raise ValueError(
                "CLIENTIFY_API_TOKEN no configurado. "
                "Definilo en .env, en .streamlit/secrets.toml, o pasalo al constructor."
            )
        self.token = token
        self.base_url = base_url.rstrip("/")

    @property
    def source_name(self) -> str:
        return "API Clientify"

    def load(self) -> pd.DataFrame:
        """Trae TODOS los contactos (paginando) y devuelve el mismo esquema
        que `ExcelContactsLoader`. Cacheado `CACHE_TTL_SECONDS` para no
        repaginar ~34k contactos en cada rerun de Streamlit.
        """
        return _cached_fetch_and_build_dataframe(self.token, self.base_url)
