"""Sección: Embudo Asignados → Calificados → Cierres."""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.filters import available_months, filter_by_month
from src.analytics.funnel import funnel_by_advisor
from src.ui.period_selector import render_period_selector
from src.utils.formatters import format_percent_raw

_TRANSPARENT = "rgba(0,0,0,0)"


def render_funnel(df_full: pd.DataFrame, default_year: int, default_month: int) -> None:
    """El "período" del embudo es el mes de CREACIÓN del lead (columna
    'creado', columna "Asignados") — a diferencia de las demás gráficas
    de esta sección, que filtran por fecha de CIERRE. Por eso reusa
    `available_months`/`filter_by_month` de `src/analytics/filters.py` (las
    mismas funciones que arman el selector global de `app.py`) en vez del
    `available_periods` de `breakdowns.py`.

    Antes recibía `df_period` ya filtrado por `app.py` al mes GLOBAL. Desde
    2026-08-14 el filtrado se hace acá adentro, después de resolver el
    período con el `st.selectbox` propio — así puede diferir del mes global
    sin desincronizarse (mismo motivo que el fix en `cierres_por_canal.py`)."""
    st.subheader("🔽 Embudo Asignados → Calificados → Cierres")

    periods = [(d.year, d.month) for d in available_months(df_full)]
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"funnel_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("Sin datos disponibles.")
        return
    year, month = sel
    df_period = filter_by_month(df_full, date(year, month, 1))

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
    display["% Efic. Bruta"] = display["% Efic. Bruta"].apply(format_percent_raw)
    st.dataframe(display, use_container_width=True, hide_index=True)
