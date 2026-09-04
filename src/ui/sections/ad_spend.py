"""Sección: Gasto en pauta publicitaria (Meta Ads)."""
from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    combine_ad_spend_sources,
    filter_by_anio_mes,
    monthly_ad_spend,
)
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

    2 selectores independientes: "Año" (`key="anio_ad_spend"`) y "Mes"
    (`key="mes_ad_spend"`), ambos con default "Todos" — con ambos en
    "Todos" se ve la tendencia completa. Año+Mes específicos combinan con
    AND (ver `ad_spend.filter_by_anio_mes`, compartida por las 6 gráficas
    de esta pestaña).
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
    # "Mes_Año" ya viene en orden cronológico (ver monthly_ad_spend).
    meses_disponibles = list(data["Mes_Año"])
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios_disponibles(meses_disponibles),
        index=0, key="anio_ad_spend",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    data = data[data["Mes_Año"].isin(labels_permitidos)]

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
