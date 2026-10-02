"""Componente Streamlit de carga de contactos desde la API de Clientify."""
import time

import pandas as pd
import streamlit as st

from src.analytics.metrics import precompute_derived_columns
from src.config.settings import CLIENTIFY_API_TOKEN, CLIENTIFY_BASE_URL
from src.data_sources.clientify_api import ClientifyAPIClient
from src.data_sources.clientify_api import clear_cache as _clear_clientify_api_cache
from src.utils.sync_timing import log_marker, timed_stage


@st.cache_data(
    ttl=900,
    show_spinner=(
        "Descargando contactos desde la API de Clientify (son ~34.000, paginados de a 250 — "
        "puede tardar varios minutos la primera vez; después queda cacheado 15 minutos)..."
    ),
)
def _load_and_prepare_from_api(token: str, base_url: str) -> pd.DataFrame:
    """Trae contactos de la API (paginado dentro de `ClientifyAPIClient.load`)
    y precalcula las columnas derivadas UNA SOLA VEZ por (token, base_url) —
    mismo patrón que `ui/upload.py::_load_and_prepare` para Excel, así
    `precompute_derived_columns` (fila por fila, ~34k contactos) no se repite
    en cada rerun de Streamlit.

    Esta función SOLO se ejecuta en un MISS del `st.cache_data` externo —
    si en los logs aparece "[SYNC] === _load_and_prepare_from_api: INICIO
    (MISS) ===", el caché externo no sirvió; si no aparece nada acá pero sí
    el tiempo total medido en `render_api_source`, fue un HIT (ver abajo).

    BUG CORREGIDO (octubre 2026): el spinner descriptivo vivía antes en un
    `with st.spinner(...):` manual, en `render_api_source`, envolviendo la
    llamada a esta función cacheada — eso lo hacía aparecer en CUALQUIER
    rerun de Streamlit (ej. al cambiar el selector Año/Mes de la gráfica
    "Gasto en pauta publicitaria", que no toca Clientify para nada), incluso
    cuando el resultado venía de cache (HIT) y la función ni se ejecutaba.
    `show_spinner` en el decorador de `st.cache_data` es la forma correcta:
    Streamlit solo lo muestra mientras el CUERPO de la función corre de
    verdad (un MISS real), nunca en un HIT.
    """
    log_marker("=== _load_and_prepare_from_api: INICIO (outer st.cache_data MISS) ===")
    with timed_stage("ClientifyAPIClient.load() (incluye inner st.cache_data + fetch/caché en disco)"):
        df = ClientifyAPIClient(token=token, base_url=base_url).load()
    with timed_stage(f"precompute_derived_columns ({len(df)} filas)"):
        out = precompute_derived_columns(df)
    log_marker("=== _load_and_prepare_from_api: FIN (MISS) ===")
    return out


def render_api_source() -> tuple[pd.DataFrame | None, str | None]:
    """
    Carga contactos desde la API de Clientify. Devuelve (df, source_name) si
    se pudo cargar, o (None, None) si falta el token o falló la conexión —
    en ambos casos mostrando un mensaje claro en vez de un traceback.
    """
    token = CLIENTIFY_API_TOKEN
    if not token:
        st.error(
            "⚠️ Falta configurar `CLIENTIFY_API_TOKEN`. Definilo en "
            "`.streamlit/secrets.toml` (desarrollo local o Streamlit Cloud) "
            "o en `.env`, y volvé a intentar."
        )
        return None, None

    try:
        outer_call_start = time.perf_counter()
        df = _load_and_prepare_from_api(token, CLIENTIFY_BASE_URL)
        outer_call_elapsed = time.perf_counter() - outer_call_start
        log_marker(
            f"render_api_source - llamada a _load_and_prepare_from_api: "
            f"{outer_call_elapsed:.2f} segundos (si no hubo logs de MISS arriba, "
            f"fue un HIT del st.cache_data externo)"
        )
        return df, "API Clientify"
    except Exception as e:
        st.error(f"❌ Error conectando con la API de Clientify: {e}")
        return None, None


def clear_api_data_cache() -> None:
    """Limpia TODOS los caches involucrados en traer datos de la API (el de
    `ClientifyAPIClient.load()` y el de `precompute_derived_columns` de acá
    encima) — usado por el botón "Actualizar datos" para forzar una recarga
    real, no solo una de las dos capas.
    """
    _load_and_prepare_from_api.clear()
    _clear_clientify_api_cache()
