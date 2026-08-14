"""Sección: Pauta vs Referidos."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.breakdowns import available_periods, pauta_vs_referidos
from src.ui.period_selector import render_period_selector

_TRANSPARENT = "rgba(0,0,0,0)"
_PRIMARY = "#2563EB"
_SUCCESS = "#16A34A"


def render_pauta_vs_referidos(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str | None = None,
) -> None:
    """`df_full` ya viene filtrado por equipo desde `app.py`. Desde
    2026-08-14 tiene su propio `st.selectbox` de "Período" — ver el mismo
    razonamiento (y el mismo fix de desincronización al sacar el antiguo
    parámetro `df_period`) en `cierres_por_canal.py`."""
    st.subheader("📡 Pauta vs Referidos")

    periods = available_periods(df_full)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"pauta_referidos_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    year, month = sel

    data = pauta_vs_referidos(df_full, df_full, year, month)
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
        # l/r chicos y simétricos (2026-08-14): antes l=80/r=120 — margen
        # muerto sobrante de una leyenda lateral que este gráfico nunca usó
        # (`showlegend=False`, las etiquetas van adentro de la dona vía
        # `texttemplate`). En un celular angosto (~340px de ancho útil) esos
        # 200px fijos dejaban la dona reducida a una fracción del contenedor.
        margin=dict(l=20, r=20, t=40, b=80),
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
