"""Sección: Gasto en pauta publicitaria (Meta Ads)."""
from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.ad_spend import combine_ad_spend_sources, monthly_ad_spend
from src.data_sources.ad_spend_loader import AdSpendLoader


@st.cache_data(show_spinner=False)
def _load_ad_spend(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Lee y normaliza el reporte de Meta Ads UNA SOLA VEZ por archivo —
    mismo patrón de cache que `src/ui/upload.py` para el Excel principal, así
    no se relee el archivo en cada rerun de Streamlit."""
    loader = AdSpendLoader(io.BytesIO(file_bytes))
    loader._name = file_name
    return loader.load()


def load_ad_spend_files(uploaded_files) -> pd.DataFrame:
    """Carga y combina (concat + dedup) los archivos de Facturación de Meta
    Ads subidos. `uploaded_files` es la lista de `UploadedFile` crudos
    guardada en `st.session_state.meta_billing_files` (o None/[] si no se
    subió nada). Devuelve DataFrame vacío si no hay archivos o ninguno pudo
    leerse.

    Compartida entre `render_ad_spend` y `render_ad_spend_vs_closures`
    (`src/ui/sections/ad_spend_vs_closures.py`) para no reimplementar el
    mismo loop de carga en dos lugares — cada archivo individual ya está
    cacheado por `_load_ad_spend`, así que llamarla más de una vez por rerun
    de Streamlit no relee los archivos.
    """
    if not uploaded_files:
        return pd.DataFrame()

    frames = []
    for uploaded_file in uploaded_files:
        try:
            frames.append(_load_ad_spend(uploaded_file.getvalue(), uploaded_file.name))
        except Exception as e:
            st.error(f"Error leyendo '{uploaded_file.name}': {e}")

    return combine_ad_spend_sources(frames)


def render_ad_spend(uploaded_files) -> None:
    """Soporta cargar el histórico de facturación junto con reportes nuevos
    de distintas cuentas: cada archivo se lee y normaliza por separado, se
    concatenan y se deduplican por 'Identificador de la transacción' para no
    sumar dos veces un cobro si los rangos de fecha de los archivos se
    solapan (ver `load_ad_spend_files`).
    """
    st.markdown("### 💰 Gasto en pauta publicitaria (Meta Ads)")

    if not uploaded_files:
        st.info(
            "Subí uno o más reportes de Facturación/Inversión de Meta Ads "
            "desde el panel lateral (histórico + reportes nuevos de cada "
            "cuenta) para ver la inversión en pauta publicitaria."
        )
        return

    raw = load_ad_spend_files(uploaded_files)
    if raw.empty:
        st.warning("No se pudo leer ningún archivo de facturación válido.")
        return

    data = monthly_ad_spend(raw)
    if data.empty:
        st.warning(
            "Los archivos se cargaron pero no se encontraron filas válidas en "
            "USD con columnas 'Fecha', 'Divisa' e 'Importe'."
        )
        return

    data = data.copy()
    # El orden de `data` ya es cronológico (ver monthly_ad_spend) — se usa
    # tal cual como categoryarray porque "Mes_Año" ("Enero 2026") no es
    # ordenable alfabéticamente de forma cronológica.
    orden_meses = list(data["Mes_Año"])

    fig = px.bar(
        data,
        x="Mes_Año",
        y="Importe",
        text="Importe",
        color="Mes_Año",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden_meses)
    fig.update_traces(texttemplate="$%{text:,.2f}", textposition="outside")
    fig.update_layout(
        template="plotly_white",
        xaxis_title="Mes y año",
        yaxis_title="Total pagado (USD)",
        xaxis_tickangle=-45,
        showlegend=False,
        bargap=0.25,
        margin=dict(t=40),
    )
    st.plotly_chart(fig, use_container_width=True)
