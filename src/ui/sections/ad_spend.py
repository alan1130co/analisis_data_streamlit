"""Sección: Gasto en pauta publicitaria (Meta Ads)."""
from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.ad_spend import monthly_ad_spend
from src.data_sources.ad_spend_loader import AdSpendLoader


@st.cache_data(show_spinner=False)
def _load_ad_spend(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Lee y normaliza el reporte de Meta Ads UNA SOLA VEZ por archivo —
    mismo patrón de cache que `src/ui/upload.py` para el Excel principal, así
    no se relee el archivo en cada rerun de Streamlit."""
    loader = AdSpendLoader(io.BytesIO(file_bytes))
    loader._name = file_name
    return loader.load()


def render_ad_spend(uploaded_file) -> None:
    """`uploaded_file` es el `UploadedFile` crudo guardado en
    `st.session_state.meta_billing_file` (o None si no se subió nada)."""
    st.markdown("### 💰 Gasto en pauta publicitaria (Meta Ads)")

    if uploaded_file is None:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver la inversión en pauta publicitaria."
        )
        return

    try:
        raw = _load_ad_spend(uploaded_file.getvalue(), uploaded_file.name)
    except Exception as e:
        st.error(f"Error leyendo el archivo de Meta Ads: {e}")
        return

    data = monthly_ad_spend(raw)
    if data.empty:
        st.warning(
            "El archivo se cargó pero no se encontraron filas válidas en USD "
            "con columnas 'Fecha', 'Divisa' e 'Importe'."
        )
        return

    data = data.copy()
    data["Importe_label"] = data["Importe"].apply(lambda x: f"${x:,.2f}")
    # El orden de `data` ya es cronológico (ver monthly_ad_spend) — se usa
    # tal cual como categoryarray porque "Mes_Año" ("Enero 2026") no es
    # ordenable alfabéticamente de forma cronológica.
    orden_meses = list(data["Mes_Año"])

    fig = px.bar(
        data,
        x="Mes_Año",
        y="Importe",
        text="Importe_label",
        title="Gasto en pauta publicitaria (Meta Ads)",
        color_discrete_sequence=px.colors.qualitative.Bold,
        category_orders={"Mes_Año": orden_meses},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(template="plotly_white")
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden_meses)
    st.plotly_chart(fig, use_container_width=True)
