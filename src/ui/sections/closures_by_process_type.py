from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.closures_by_process_type import (
    CATEGORY_COLUMN,
    CATEGORY_LABEL,
    available_periods,
    closures_by_process_type,
)
from src.ui.period_selector import format_period_label, render_period_selector

_PALETTE = [
    "#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#0891B2",
    "#DC2626", "#D97706", "#059669", "#9333EA", "#E11D48",
    "#94A3B8", "#0EA5E9", "#10B981", "#F59E0B", "#A855F7",
]


def render_closures_by_process_type(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str = "Todos",
) -> None:
    st.markdown("### 📋 Cierres por Tipo de Proceso")

    if CATEGORY_COLUMN not in df_full.columns:
        st.info(f"La columna '{CATEGORY_COLUMN}' no existe en los datos cargados.")
        return

    periods = available_periods(df_full)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"closures_process_type_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    sel_year, sel_month = sel
    selected_label = format_period_label(sel_year, sel_month)

    dist = closures_by_process_type(df_full, sel_year, sel_month, team)

    if dist.empty:
        st.info(f"No hay cierres en {selected_label} para el equipo {team}.")
        return

    # Detalle completo (categoría + cantidad + %) va al hover, no a la
    # leyenda — con hasta 15 categorías, una leyenda de frases largas tipo
    # "Categoría — N cierres (X%)" es justo lo que se amontona en un
    # celular angosto. La leyenda ahora solo lleva el nombre corto.
    dist["Etiqueta"] = dist.apply(
        lambda r: f"{r[CATEGORY_LABEL]} — {int(r['Total'])} cierres ({r['Porcentaje']}%)",
        axis=1,
    )
    total = int(dist["Total"].sum())

    fig = go.Figure(data=[go.Pie(
        labels=dist[CATEGORY_LABEL],
        values=dist["Total"],
        hole=0.4,
        sort=False,
        marker=dict(colors=_PALETTE[:len(dist)], line=dict(color="white", width=2)),
        textinfo="none",
        hovertext=dist["Etiqueta"],
        hovertemplate="%{hovertext}<extra></extra>",
    )])
    fig.update_layout(
        height=520,
        # Leyenda horizontal debajo del gráfico en vez de columna vertical
        # fija a la derecha (2026-08-14): antes `legend=dict(orientation=
        # "v", x=1.02, ...)` con margin r=140 reservaba ~140px fijos de
        # ancho para la leyenda — en un celular (~340px de ancho útil) eso
        # dejaba la dona reducida a una fracción mínima del contenedor. Una
        # leyenda horizontal debajo hace wrap solo (varias filas) a
        # cualquier ancho, igual que ya usan `funnel.py`/`trend.py`/
        # `comparison.py`/`leads_summary.py` — margen extra en `b` para el
        # espacio que ocupa esa leyenda envuelta.
        margin=dict(l=20, r=20, t=20, b=100),
        showlegend=True,
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.12, font=dict(size=11)),
        annotations=[dict(
            text=f"<b>{total}</b><br>Cierres",
            x=0.5, y=0.5, font_size=15, showarrow=False,
        )],
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Mostrando {total} cierres en {selected_label} para {team}.")
