"""Sección: Ventas diarias del mes."""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics.daily_sales import daily_sales_by_advisor, daily_sales_total

_TRANSPARENT = "rgba(0,0,0,0)"

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}
_MONTH_VALUES = list(_MONTHS_ES.values())
_MONTH_KEYS = list(_MONTHS_ES.keys())


def render_daily_sales(df_full: pd.DataFrame, selected_month: date) -> None:
    """
    df_full: dataset filtrado por equipo (todas las fechas).
    selected_month: mes seleccionado en el dashboard (default para los selectores).
    """
    st.subheader("📅 Ventas diarias")

    if df_full.empty:
        st.info("No hay datos disponibles.")
        return

    year_opts: list[int] = []
    if "creado" in df_full.columns:
        parsed = pd.to_datetime(df_full["creado"], errors="coerce")
        year_opts = sorted(parsed.dt.year.dropna().unique().astype(int).tolist())
    if not year_opts:
        year_opts = [selected_month.year]

    c1, c2 = st.columns(2)
    with c1:
        default_year_idx = year_opts.index(selected_month.year) if selected_month.year in year_opts else len(year_opts) - 1
        year_sel = st.selectbox(
            "Año", year_opts, index=default_year_idx,
            key=f"daily_year_{selected_month.year}_{selected_month.month}",
        )
    with c2:
        month_label = st.selectbox(
            "Mes",
            _MONTH_VALUES,
            index=selected_month.month - 1,
            key=f"daily_month_{selected_month.year}_{selected_month.month}",
        )
        month_sel = _MONTH_KEYS[_MONTH_VALUES.index(month_label)]

    data_total = daily_sales_total(df_full, year_sel, month_sel)

    if data_total.empty:
        st.info("No hay cierres registrados para ese mes.")
        return

    fig1 = px.bar(
        data_total,
        x="dia",
        y="Cierres",
        color="Cierres",
        color_continuous_scale="Blues",
        text="Cierres",
        height=350,
    )
    fig1.update_traces(textposition="outside")
    fig1.update_layout(
        margin=dict(l=0, r=20, t=20, b=20),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        coloraxis_showscale=False,
        xaxis_title="Día",
    )
    st.plotly_chart(fig1, use_container_width=True)

    data_adv = daily_sales_by_advisor(df_full, year_sel, month_sel)
    if not data_adv.empty:
        data_adv = data_adv.copy()
        data_adv["propietario"] = data_adv["propietario"].apply(
            lambda x: str(x).title() if pd.notna(x) else x
        )
        fig2 = px.bar(
            data_adv,
            x="dia",
            y="Cierres",
            color="propietario",
            barmode="stack",
            height=350,
            labels={"propietario": "Asesor", "dia": "Día"},
        )
        fig2.update_layout(
            margin=dict(l=0, r=20, t=20, b=20),
            plot_bgcolor=_TRANSPARENT,
            paper_bgcolor=_TRANSPARENT,
        )
        st.plotly_chart(fig2, use_container_width=True)
