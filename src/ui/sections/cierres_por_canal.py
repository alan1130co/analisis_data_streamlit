"""Sección: Cierres por canal."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.breakdowns import cierres_por_canal

_TRANSPARENT = "rgba(0,0,0,0)"
_COLORS_10 = [
    "#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#0891B2",
    "#DC2626", "#D97706", "#059669", "#9333EA", "#E11D48",
]


def render_cierres_por_canal(
    df_period: pd.DataFrame,
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Marketing (pautas)",
) -> None:
    st.subheader("📋 Cierres por canal")

    data = cierres_por_canal(df_period, df_full, year, month, team=team)
    if data.empty:
        st.info("No hay cierres registrados en el período.")
        return

    total = int(data["Cantidad"].sum())
    colors = [_COLORS_10[i % len(_COLORS_10)] for i in range(len(data))]

    col_chart, col_table = st.columns([3, 2])

    with col_chart:
        fig = go.Figure(go.Pie(
            labels=data["Canal"],
            values=data["Cantidad"],
            hole=0.55,
            pull=[0.04] * len(data),
            marker_colors=colors,
            texttemplate="%{label}<br>%{value}",
            textfont=dict(size=9),
            hovertemplate="%{label}: %{value} cierres (%{percent})<extra></extra>",
        ))
        fig.add_annotation(
            text=f"<b>{total}</b><br>Cierres",
            x=0.5, y=0.5,
            font_size=14,
            showarrow=False,
            xanchor="center",
            yanchor="middle",
        )
        fig.update_layout(
            height=460,
            margin=dict(l=80, r=140, t=40, b=80),
            showlegend=False,
            plot_bgcolor=_TRANSPARENT,
            paper_bgcolor=_TRANSPARENT,
            legend=dict(orientation="v", x=1.05, y=0.5, font=dict(size=10)),
            uniformtext_minsize=10,
            uniformtext_mode="hide",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.caption("Detalle por canal")
        display = data[["Canal", "Cantidad"]].rename(columns={"Cantidad": "Cierres"})
        st.dataframe(display, use_container_width=True, hide_index=True)
