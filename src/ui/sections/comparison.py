"""Sección: Comparación contra mes anterior."""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.comparison import monthly_comparison
from src.analytics.filters import previous_month

_TRANSPARENT = "rgba(0,0,0,0)"

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}
_MONTH_VALUES = list(_MONTHS_ES.values())
_MONTH_KEYS = list(_MONTHS_ES.keys())


def render_comparison(df_unfiltered: pd.DataFrame, selected_month: date) -> None:
    st.subheader("📆 Comparación contra mes anterior")

    parsed = pd.to_datetime(df_unfiltered.get("creado", pd.Series(dtype="object")), errors="coerce")
    years = sorted(parsed.dt.year.dropna().unique().astype(int).tolist())

    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        year_idx = years.index(selected_month.year) if selected_month.year in years else len(years) - 1
        year_sel = st.selectbox(
            "Año", years, index=year_idx,
            key=f"comparison_year_{selected_month.year}_{selected_month.month}",
        )
    with c2:
        month_label = st.selectbox(
            "Mes", _MONTH_VALUES,
            index=selected_month.month - 1,
            key=f"comparison_month_{selected_month.year}_{selected_month.month}",
        )
        month_sel = _MONTH_KEYS[_MONTH_VALUES.index(month_label)]

    chosen_month = date(year_sel, month_sel, 1)
    data = monthly_comparison(df_unfiltered, chosen_month)

    if data.empty:
        st.info("No hay mes anterior disponible para comparar.")
        return

    prev = previous_month(chosen_month)
    prev_label = prev.strftime("%B %Y").capitalize()
    curr_label = chosen_month.strftime("%B %Y").capitalize()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=prev_label,
        x=data["Indicador"],
        y=data["mes_anterior"],
        marker_color="#94A3B8",
        text=data["mes_anterior"],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name=curr_label,
        x=data["Indicador"],
        y=data["mes_actual"],
        marker_color="#2563EB",
        text=data["mes_actual"],
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        height=400,
        xaxis_tickangle=-15,
        margin=dict(l=0, r=20, t=30, b=40),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
