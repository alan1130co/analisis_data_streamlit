"""Selector de fuente de gasto en pauta: API de Meta Ads (Insights, gasto
real diario) o subida manual de CSV/Excel de Facturación.

Mismo patrón que `src/ui/data_source_selector.py` + `src/ui/api_source.py`
(Excel vs API de Clientify): un radio + el control que corresponda, un
botón "Actualizar datos de Meta" para forzar un refresh de la fuente API
(análogo a "Actualizar datos"), y `@st.cache_data(ttl=900)` para no
repaginar las 3 cuentas en cada rerun de Streamlit.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config.settings import APP_TIMEZONE, META_ACCESS_TOKEN
from src.data_sources.meta_ads_api import DEFAULT_SINCE, MetaAdsAPIError, fetch_meta_ad_spend
from src.ui.sections.ad_spend import load_ad_spend_files
from src.utils.sync_timing import log_marker, timed_stage

API_OPTION = "API de Meta"
CSV_OPTION = "Subir CSV"

CACHE_TTL_SECONDS = 900


@st.cache_data(
    ttl=CACHE_TTL_SECONDS,
    show_spinner="Descargando gasto real de Meta Ads (Insights, 3 cuentas en paralelo)...",
)
def _cached_fetch_meta_ad_spend(token: str, since: str, until: str) -> tuple[pd.DataFrame, list[str], str]:
    """Trae y agrega el gasto — cacheado 15 minutos. El tercer valor
    (`fetched_at`) se calcula DENTRO de la función cacheada a propósito:
    así solo cambia en un cache MISS real, y sirve como "hora de la última
    actualización" mostrada en la UI."""
    log_marker("=== _cached_fetch_meta_ad_spend: INICIO (MISS) ===")
    with timed_stage("fetch_meta_ad_spend (3 cuentas en paralelo)"):
        df, warnings = fetch_meta_ad_spend(token=token, since=since, until=until)
    fetched_at = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    log_marker(f"=== _cached_fetch_meta_ad_spend: FIN (MISS) — {len(df)} días, {len(warnings)} advertencia(s) ===")
    return df, warnings, fetched_at


def clear_meta_api_cache() -> None:
    """Limpia el cache de `_cached_fetch_meta_ad_spend` — usado por el botón
    "Actualizar datos de Meta" para forzar una recarga inmediata."""
    _cached_fetch_meta_ad_spend.clear()


def render_meta_ads_source() -> tuple[pd.DataFrame, list, str]:
    """Renderiza el selector "Fuente de gasto en pauta" + el control que
    corresponda. Debe llamarse ya dentro de un `with st.sidebar:`.

    Devuelve `(gasto_raw, meta_billing_files, source_label)`:
      - `gasto_raw`: DataFrame listo para pasar a TODAS las gráficas de
        "Marketing e Inversión" sin importar la fuente — con CSV es el
        esquema crudo del export de Meta Ads Manager (como siempre); con
        API ya viene en el esquema de `ad_spend.prepare_ad_spend`
        (compatible: esa función es idempotente sobre su propia salida).
      - `meta_billing_files`: lista cruda de archivos subidos (solo con
        CSV_OPTION; `None` con API_OPTION) — se sigue pasando tal cual a
        `render_ad_spend` para no tocar su firma ni sus tests existentes.
      - `source_label`: `API_OPTION` o `CSV_OPTION`, la fuente elegida.
    """
    st.markdown("### 💰 Facturación / Inversión (Meta Ads)")

    # Por defecto, API si hay credenciales configuradas; si no, CSV.
    default_index = 0 if META_ACCESS_TOKEN else 1
    source = st.radio(
        "Fuente de gasto en pauta",
        options=[API_OPTION, CSV_OPTION],
        index=default_index,
        key="meta_ads_source",
    )

    if source == CSV_OPTION:
        meta_billing_files = st.file_uploader(
            "Cargar reportes de Facturación/Inversión (Meta Ads)",
            type=["csv", "xls", "xlsx"],
            key="meta_billing_uploader",
            accept_multiple_files=True,
            help=(
                "Podés cargar varios archivos a la vez: el histórico de "
                "facturación y los reportes nuevos de cada cuenta "
                "(columnas Fecha, Divisa, Importe)."
            ),
        )
        st.session_state.meta_billing_files = meta_billing_files
        with timed_stage("load_ad_spend_files (Meta Ads, CSV)"):
            gasto_raw = load_ad_spend_files(meta_billing_files)
        return gasto_raw, meta_billing_files, source

    # API_OPTION
    st.session_state.meta_billing_files = None

    if not META_ACCESS_TOKEN:
        st.error(
            "⚠️ Falta configurar `META_ACCESS_TOKEN`. Definilo en "
            "`.streamlit/secrets.toml` (desarrollo local o Streamlit Cloud) "
            "o en `.env` — o elegí 'Subir CSV' mientras tanto."
        )
        return pd.DataFrame(), None, source

    until = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d")
    try:
        with timed_stage("_cached_fetch_meta_ad_spend (Meta Ads, API)"):
            df, warnings, fetched_at = _cached_fetch_meta_ad_spend(META_ACCESS_TOKEN, DEFAULT_SINCE, until)
    except MetaAdsAPIError as exc:
        st.error(f"❌ Error conectando con la API de Meta Ads: {exc}")
        return pd.DataFrame(), None, source

    for warning in warnings:
        st.warning(f"⚠️ {warning}")

    if not df.empty:
        fecha_min = df["Fecha"].min().strftime("%Y-%m-%d")
        fecha_max = df["Fecha"].max().strftime("%Y-%m-%d")
        st.caption(f"📅 Rango cubierto: {fecha_min} a {fecha_max}. Última actualización: {fetched_at}.")
    else:
        st.caption(f"Última actualización: {fetched_at}.")

    if st.button("🔄 Actualizar datos de Meta", use_container_width=True):
        clear_meta_api_cache()
        st.rerun()

    return df, None, source
