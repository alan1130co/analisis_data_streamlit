"""Componente Streamlit de carga de archivo Excel."""
import streamlit as st
import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader


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
        loader = ExcelContactsLoader(uploaded)
        with st.spinner("Procesando archivo..."):
            df = loader.load()
        return df, loader.source_name
    except Exception as e:
        st.error(f"Error leyendo el archivo: {e}")
        return None, None
