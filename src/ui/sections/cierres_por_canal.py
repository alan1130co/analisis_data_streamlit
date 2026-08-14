"""Sección: Cierres por canal."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.breakdowns import available_periods, cierres_por_canal
from src.ui.period_selector import format_period_label, render_period_selector

_TRANSPARENT = "rgba(0,0,0,0)"
_COLORS_10 = [
    "#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#0891B2",
    "#DC2626", "#D97706", "#059669", "#9333EA", "#E11D48",
]


def render_cierres_por_canal(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str = "Marketing (pautas)",
) -> None:
    """`df_full` ya viene filtrado por equipo desde `app.py` (igual que
    antes). Desde 2026-08-14 esta gráfica tiene su propio `st.selectbox` de
    "Período" (mismo patrón que `closures_by_state.py` y el resto de los
    desgloses) en vez de seguir obligatoriamente al selector global — el mes
    global sigue siendo el default.

    Antes recibía también `df_period` (el df ya filtrado al mes GLOBAL, vía
    `filter_by_month`) solo para un chequeo `.empty` — con el selector local
    nuevo eso quedó roto: si el usuario elegía acá un mes distinto al
    global, `df_period` seguía atado al mes global y podía dar `.empty` pese
    a que `df_full` sí tenía cierres para el mes recién elegido. Se sacó ese
    parámetro; `cierres_por_canal()` ya filtra todo lo que necesita de
    `df_full` por `year`/`month`."""
    st.subheader("📋 Cierres por canal")

    periods = available_periods(df_full)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"cierres_canal_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    year, month = sel

    data = cierres_por_canal(df_full, df_full, year, month, team=team)
    if data.empty:
        st.info(f"No hay cierres registrados en {format_period_label(year, month)}.")
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
            # l/r chicos y simétricos (2026-08-14): antes l=80/r=140 más un
            # `legend=dict(...)` de leyenda lateral vertical que nunca se
            # mostraba (`showlegend=False` — las etiquetas van adentro de la
            # dona vía `texttemplate`). Margen muerto que en un celular
            # angosto dejaba la dona reducida a una fracción del ancho real
            # disponible (esta sección además vive en `col_chart` de un
            # `st.columns([3, 2])`, que en mobile pasa a ocupar el 100% del
            # ancho de pantalla, no 3/5 — el margen fijo pesa proporcionalmente
            # mucho más ahí que en desktop).
            margin=dict(l=20, r=20, t=40, b=80),
            showlegend=False,
            plot_bgcolor=_TRANSPARENT,
            paper_bgcolor=_TRANSPARENT,
            uniformtext_minsize=10,
            uniformtext_mode="hide",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.caption("Detalle por canal")
        display = data[["Canal", "Cantidad"]].rename(columns={"Cantidad": "Cierres"})
        st.dataframe(display, use_container_width=True, hide_index=True)
