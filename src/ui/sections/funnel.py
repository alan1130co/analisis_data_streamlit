"""Sección: Embudo Asignados → Calificados → Cierres."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.funnel import funnel_by_advisor
from src.utils.formatters import format_percent_raw

_TRANSPARENT = "rgba(0,0,0,0)"


def render_funnel(df_period: pd.DataFrame, df_full: pd.DataFrame, year: int, month: int) -> None:
    st.subheader("🔽 Embudo Asignados → Calificados → Cierres")

    data = funnel_by_advisor(df_period, df_full, year, month)

    if data.empty:
        st.info("Sin asesores con leads asignados en este período.")
        return

    _SERIES = [
        ("Asignados",        "#94A3B8"),
        ("Calificados",      "#2563EB"),
        ("Cierres Pauta",    "#F59E0B"),
        ("Cierres Totales",  "#16A34A"),
    ]

    fig = go.Figure()
    for col, color in _SERIES:
        if col in data.columns:
            fig.add_trace(go.Bar(
                name=col,
                x=data["Asesor"],
                y=data[col],
                marker_color=color,
                text=data[col],
                textposition="outside",
            ))

    fig.update_layout(
        barmode="group",
        height=420,
        xaxis_tickangle=-30,
        margin=dict(l=0, r=20, t=40, b=60),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    display = data.copy()
    display["% Eficiencia Real"] = display["% Eficiencia Real"].apply(format_percent_raw)
    display["% Efic. Global"] = display["% Efic. Global"].apply(format_percent_raw)
    st.dataframe(display, use_container_width=True, hide_index=True)
