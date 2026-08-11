"""Sección: Cierres vs Segundos Cierres por Año-Mes."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.closures_vs_second_closures import closures_vs_second_closures


def render_closures_vs_second_closures(df: pd.DataFrame) -> None:
    st.markdown("### 📊 Cierres vs Segundos Cierres por Año-Mes")

    data = closures_vs_second_closures(df)
    if data.empty:
        st.info("No hay cierres registrados para comparar.")
        return

    fig = px.bar(
        data,
        x="Año-Mes",
        y=["Cierres", "Segundos cierres"],
        barmode="group",
        text_auto=True,
        title="Cierres y Segundos Cierres por Año-Mes",
    )
    fig.update_layout(xaxis={"type": "category"})
    st.plotly_chart(fig, use_container_width=True)
