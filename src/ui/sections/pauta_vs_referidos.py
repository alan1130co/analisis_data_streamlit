"""Sección: Pauta vs Referidos."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.breakdowns import pauta_vs_referidos

_TRANSPARENT = "rgba(0,0,0,0)"
_PRIMARY = "#2563EB"
_SUCCESS = "#16A34A"


def render_pauta_vs_referidos(
    df_period: pd.DataFrame,
    df_full: pd.DataFrame,
    team: str | None = None,
) -> None:
    st.subheader("📡 Pauta vs Referidos")

    data = pauta_vs_referidos(df_period, df_full)
    pauta_row = data[data["Origen"] == "Pauta"].iloc[0]
    ref_row = data[data["Origen"] == "Referidos"].iloc[0]
    total = int(pauta_row["Cantidad"]) + int(ref_row["Cantidad"])

    fig = go.Figure(go.Pie(
        labels=data["Origen"],
        values=data["Cantidad"],
        hole=0.62,
        pull=[0.06, 0.06],
        marker_colors=[_PRIMARY, _SUCCESS],
        texttemplate="%{label}<br>%{value} (%{percent})",
        hovertemplate="%{label}: %{value} cierres (%{percent})<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{total}</b><br>Cierres",
        x=0.5, y=0.5,
        font_size=15,
        showarrow=False,
        xanchor="center",
        yanchor="middle",
    )
    fig.update_layout(
        height=480,
        margin=dict(l=80, r=120, t=40, b=80),
        showlegend=False,
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        uniformtext_minsize=11,
        uniformtext_mode="hide",
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Pauta",     f"{int(pauta_row['Cantidad']):,}".replace(",", "."))
    c2.metric("Referidos", f"{int(ref_row['Cantidad']):,}".replace(",", "."))
    c3.metric("Total",     f"{total:,}".replace(",", "."))
