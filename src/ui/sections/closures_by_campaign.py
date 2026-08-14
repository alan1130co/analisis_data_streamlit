"""Sección: Cierres por Campaña - pauta."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.closures_by_campaign import (
    CATEGORY_COLUMN,
    CATEGORY_LABEL,
    available_periods,
    closures_by_campaign,
)
from src.ui.period_selector import format_period_label, render_period_selector

_BAR_COLOR = "#2563EB"
_TRANSPARENT = "rgba(0,0,0,0)"
_TOP_N = 15


def render_closures_by_campaign(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str = "Todos",
) -> None:
    """Desde 2026-08-14 tiene su propio `st.selectbox` de "Período" (mismo
    patrón que `closures_by_state.py` y el resto de los desgloses) en vez de
    seguir obligatoriamente al selector global — el mes global sigue siendo
    el default. `available_periods` ya existía en
    `analytics/closures_by_campaign.py` pero no estaba conectada a la UI."""
    st.markdown("### 🎯 Cierres por Campaña")

    if CATEGORY_COLUMN not in df_full.columns:
        st.info(f"La columna '{CATEGORY_COLUMN}' no existe en los datos cargados.")
        return

    periods = available_periods(df_full)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"closures_campaign_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres de campañas registrados.")
        return
    year, month = sel

    dist = closures_by_campaign(df_full, year, month, team)

    if dist.empty:
        st.info(f"No hay cierres de campañas registrados en {format_period_label(year, month)}.")
        return

    total = int(dist["Total"].sum())

    # Muchas campañas pueden coexistir en un mes (una por creativo/set) — se
    # muestran las top N por cierres y el resto se agrupa en "Otras campañas"
    # para que el gráfico de barras siga siendo legible.
    if len(dist) > _TOP_N:
        top = dist.iloc[:_TOP_N].copy()
        resto_total = int(dist.iloc[_TOP_N:]["Total"].sum())
        resto_pct = round(resto_total / total * 100, 1) if total else 0.0
        otras = pd.DataFrame([{CATEGORY_LABEL: "Otras campañas", "Total": resto_total, "Porcentaje": resto_pct}])
        plot_data = pd.concat([top, otras], ignore_index=True)
    else:
        plot_data = dist

    # Orden ascendente para que la barra con más cierres quede arriba en un
    # gráfico horizontal (Plotly dibuja de abajo hacia arriba).
    plot_data = plot_data.iloc[::-1]

    col_chart, col_table = st.columns([3, 2])

    with col_chart:
        fig = go.Figure(go.Bar(
            x=plot_data["Total"],
            y=plot_data[CATEGORY_LABEL],
            orientation="h",
            marker_color=_BAR_COLOR,
            text=plot_data["Total"],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x} cierres<extra></extra>",
        ))
        fig.update_layout(
            height=max(320, 34 * len(plot_data)),
            margin=dict(l=10, r=40, t=20, b=40),
            plot_bgcolor=_TRANSPARENT,
            paper_bgcolor=_TRANSPARENT,
            xaxis=dict(title="Cierres", showgrid=True, gridcolor="rgba(148,163,184,0.25)"),
            yaxis=dict(title=""),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.caption("Detalle por campaña")
        display = dist[[CATEGORY_LABEL, "Total", "Porcentaje"]].rename(columns={"Total": "Cierres", "Porcentaje": "%"})
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.caption(f"Mostrando {total} cierres en {format_period_label(year, month)} para {team}.")
