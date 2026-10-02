"""Selector de fuente de datos: Excel subido o API de Clientify.

Encapsulado en su propio componente (en vez de vivir inline en app.py) para
poder testearlo con AppTest sin depender del resto de la app (auth, tabs,
secciones) — ver tests/test_data_source_selector_ui.py.
"""
import pandas as pd
import streamlit as st

from src.ui.api_source import clear_api_data_cache, render_api_source
from src.ui.upload import render_upload

EXCEL_OPTION = "Subir Excel"
API_OPTION = "Conectar con Clientify API"


def render_data_source_selector() -> tuple[pd.DataFrame | None, str | None]:
    """Renderiza el radio de fuente + el control que corresponda (uploader
    para Excel, o carga+botón "Actualizar datos" para la API), y actualiza
    `st.session_state.df`/`st.session_state.source_name`.

    Devuelve (df, source_name) — el estado actual en session_state, para que
    el resto de `app.py` no necesite leerlo por su cuenta.
    """
    if "df" not in st.session_state:
        st.session_state.df = None
        st.session_state.source_name = None

    st.header("Fuente de datos")
    source = st.radio(
        "¿De dónde cargar los datos?",
        options=[EXCEL_OPTION, API_OPTION],
        index=0,
    )

    if source == EXCEL_OPTION:
        df, source_name = render_upload()
    else:
        df, source_name = render_api_source()

    if df is not None:
        st.session_state.df = df
        st.session_state.source_name = source_name

    if st.session_state.df is not None:
        st.success(f"✅ Datos cargados: {st.session_state.source_name}")
        st.caption(f"{len(st.session_state.df):,} registros")

        # El botón de refresh solo tiene sentido para la API (el Excel ya se
        # recarga solo al subir un archivo nuevo, vía _load_and_prepare cacheado
        # por (file_bytes, file_name)).
        if source == EXCEL_OPTION:
            if st.button("🔄 Cargar otro archivo", use_container_width=True):
                st.session_state.df = None
                st.session_state.source_name = None
                st.rerun()
        else:
            if st.button("🔄 Actualizar datos", use_container_width=True):
                clear_api_data_cache()
                st.rerun()

    return st.session_state.df, st.session_state.source_name
