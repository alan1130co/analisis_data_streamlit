"""Componente Streamlit de carga de archivo Excel."""
import io

import streamlit as st
import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.metrics import precompute_derived_columns


@st.cache_data(show_spinner=False)
def _load_and_prepare(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Parsea el Excel y precalcula las columnas derivadas UNA SOLA VEZ por
    archivo. `st.cache_data` cachea el resultado por (file_bytes, file_name):
    Streamlit vuelve a ejecutar `app.py` completo en CADA interacción del
    usuario (cambiar el mes, tocar cualquier otro filtro/uploader de la
    barra lateral), y sin este cache el archivo de Excel se releía y
    reprocesaba desde cero en cada una de esas reejecuciones — esa relectura
    redundante era la causa principal de que la UI se congelara al cambiar
    de mes."""
    loader = ExcelContactsLoader(io.BytesIO(file_bytes))
    loader._name = file_name  # para que source_name devuelva el nombre real
    df = loader.load()
    return precompute_derived_columns(df)


def render_upload() -> tuple[pd.DataFrame | None, str | None]:
    """
    Renderiza el uploader. Devuelve (df, source_name) si hay archivo cargado,
    o (None, None) si no.
    """
    uploaded = st.file_uploader(
        "Subí el archivo de contactos",
        type=["xls", "xlsx"],
        help="Exportación de Clientify de la sección Contactos",
    )

    if uploaded is None:
        return None, None

    try:
        with st.spinner("Procesando archivo..."):
            df = _load_and_prepare(uploaded.getvalue(), uploaded.name)
        return df, uploaded.name
    except Exception as e:
        st.error(f"Error leyendo el archivo: {e}")
        return None, None
