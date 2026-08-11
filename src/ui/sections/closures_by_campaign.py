"""Sección: Cierres por Campaña - pauta."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.closures_by_campaign import (
    CATEGORY_COLUMN,
    CATEGORY_LABEL,
    closures_by_campaign,
)

_BAR_COLOR = "#2563EB"
_TRANSPARENT = "rgba(0,0,0,0)"
_TOP_N = 15


def render_closures_by_campaign(
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Todos",
) -> None:
    """Sigue el mismo período (año/mes) y filtro de equipo que el resto del
    dashboard — sin selector propio — para que se actualice junto con las
    demás secciones al cambiar el mes en el filtro principal."""
    st.markdown("### 🎯 Cierres por Campaña")

    if CATEGORY_COLUMN not in df_full.columns:
        st.info(f"La columna '{CATEGORY_COLUMN}' no existe en los datos cargados.")
        return

    dist = closures_by_campaign(df_full, year, month, team)

    if dist.empty:
        st.info("No hay cierres de campañas registrados en el período.")
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

    st.caption(f"Mostrando {total} cierres en el período seleccionado para {team}.")
