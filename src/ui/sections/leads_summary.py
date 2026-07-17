"""Sección: Leads por mes y año."""
from __future__ import annotations

import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.leads_summary import leads_summary

_TRANSPARENT = "rgba(0,0,0,0)"

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}
_MONTH_VALUES = list(_MONTHS_ES.values())
_MONTH_KEYS = list(_MONTHS_ES.keys())


def render_leads_summary(
    df_unfiltered: pd.DataFrame,
    default_month: datetime.date | None = None,
) -> None:
    st.subheader("📋 Leads por mes y año")

    if "creado" not in df_unfiltered.columns or df_unfiltered.empty:
        st.info("No hay datos disponibles.")
        return

    parsed = pd.to_datetime(df_unfiltered["creado"], errors="coerce")
    years = sorted(parsed.dt.year.dropna().unique().astype(int).tolist(), reverse=True)
    if not years:
        st.info("No hay datos con fecha válida.")
        return

    default_suffix = f"{default_month.year}_{default_month.month}" if default_month else "none"

    c1, c2 = st.columns(2)
    with c1:
        year_idx = years.index(default_month.year) if default_month and default_month.year in years else 0
        year_sel = st.selectbox("Año", years, index=year_idx, key=f"leads_summary_year_{default_suffix}")
    with c2:
        month_opts = ["Todos"] + _MONTH_VALUES
        month_idx = default_month.month if default_month else 0
        month_label = st.selectbox("Mes", month_opts, index=month_idx, key=f"leads_summary_month_{default_suffix}")
        month_sel = None if month_label == "Todos" else _MONTH_KEYS[_MONTH_VALUES.index(month_label)]

    data = leads_summary(df_unfiltered, year_sel, month=month_sel)

    if data.empty:
        st.info("No hay datos para la selección.")
        return

    _SERIES = [
        ("Leads",       "#94A3B8"),
        ("Calificados", "#2563EB"),
        ("Cierres",     "#16A34A"),
        ("Referidos",   "#7C3AED"),
    ]

    fig = go.Figure()
    for col, color in _SERIES:
        if col in data.columns:
            fig.add_trace(go.Bar(
                name=col,
                x=data["mes"],
                y=data[col],
                marker_color=color,
                text=data[col],
                textposition="outside",
            ))

    fig.update_layout(
        barmode="group",
        height=380,
        margin=dict(l=0, r=20, t=30, b=20),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(data, use_container_width=True, hide_index=True)
