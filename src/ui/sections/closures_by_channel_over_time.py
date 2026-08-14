"""Sección: Cierres por canal (Pauta directa vs Referidos) en el tiempo."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.closures_by_channel_over_time import closures_by_channel_over_time

_COLOR_MAP = {
    "Primer cierre": "#1F77B4",
    "Segundo cierre": "#FF7F0E",
    "Tercer cierre": "#2CA02C",
    "Cuarto cierre": "#9467BD",
}
_TIPO_ORDER = ["Primer cierre", "Segundo cierre", "Tercer cierre", "Cuarto cierre"]


def render_closures_by_channel_over_time(df: pd.DataFrame) -> None:
    st.markdown("### 📈 Cierres por canal (Pauta directa vs Referidos)")

    data = closures_by_channel_over_time(df)
    if data.empty:
        st.info("No hay cierres registrados para comparar.")
        return

    # Orden explícito por Año-Mes/Canal antes de graficar — junto con
    # `category_orders` y `categoryorder='category ascending'` más abajo,
    # esto evita que Plotly reordene el eje X alfabéticamente por sus
    # propios criterios en vez de respetar la línea de tiempo.
    data = data.sort_values(["Año-Mes", "Canal"])

    fig = px.bar(
        data,
        x="Año-Mes",
        y="Total cierres",
        color="Tipo",
        facet_col="Canal",
        text="Total cierres",
        color_discrete_map=_COLOR_MAP,
        category_orders={
            "Año-Mes": sorted(data["Año-Mes"].unique()),
            "Tipo": _TIPO_ORDER,
        },
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(template="plotly_white", margin=dict(t=60))
    fig.update_xaxes(type="category", categoryorder="category ascending")
    st.plotly_chart(fig, use_container_width=True)
