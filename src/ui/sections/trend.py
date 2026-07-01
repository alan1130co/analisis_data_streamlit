"""Sección: Tendencia mensual con doble eje Y."""
from __future__ import annotations

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.analytics.trend import monthly_trend

_TRANSPARENT = "rgba(0,0,0,0)"

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}
_MONTH_VALUES = list(_MONTHS_ES.values())
_MONTH_KEYS = list(_MONTHS_ES.keys())


def render_trend(
    df_unfiltered: pd.DataFrame,
    default_month: datetime.date | None = None,
) -> None:
    st.subheader("📈 Tendencia mensual")

    today = datetime.date.today()
    default_year = default_month.year if default_month else today.year
    default_m = default_month.month if default_month else today.month

    c1, c2 = st.columns(2)
    with c1:
        year_end = st.selectbox(
            "Año fin",
            list(range(2024, today.year + 2)),
            index=list(range(2024, today.year + 2)).index(default_year),
            key="trend_year_end",
        )
    with c2:
        month_label = st.selectbox(
            "Mes fin",
            _MONTH_VALUES,
            index=default_m - 1,
            key="trend_month_end",
        )
        month_end = _MONTH_KEYS[_MONTH_VALUES.index(month_label)]

    data = monthly_trend(df_unfiltered, year_end, month_end)

    if data.empty:
        st.info("No hay datos para el rango seleccionado.")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=data["mes"], y=data["Asignados"],
            name="Asignados",
            line=dict(color="#94A3B8", width=1.5),
            mode="lines+markers",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=data["mes"], y=data["Calificados"],
            name="Calificados",
            line=dict(color="#2563EB", width=2),
            mode="lines+markers",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=data["mes"], y=data["Cierres"],
            name="Cierres",
            line=dict(color="#16A34A", width=3),
            mode="lines+markers+text",
            marker=dict(size=10),
            text=data["Cierres"],
            textposition="top center",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        height=420,
        margin=dict(l=0, r=60, t=30, b=20),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_yaxes(title_text="Asignados / Calificados", secondary_y=False)
    fig.update_yaxes(title_text="Cierres", secondary_y=True, rangemode="tozero")

    st.plotly_chart(fig, use_container_width=True)
    st.caption("Tendencia desde mayo 2024 (inicio de operaciones) hasta el mes seleccionado.")
