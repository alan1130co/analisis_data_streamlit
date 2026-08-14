from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.closures_by_sector import (
    CATEGORY_COLUMN,
    CATEGORY_LABEL,
    available_periods,
    closures_by_sector,
)
from src.ui.period_selector import format_period_label, render_period_selector

_TRANSPARENT = "rgba(0,0,0,0)"
_COLORS_15 = [
    "#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#0891B2",
    "#DC2626", "#D97706", "#059669", "#9333EA", "#E11D48",
    "#0EA5E9", "#65A30D", "#DB2777", "#4F46E5", "#EAB308",
]


def render_closures_by_sector(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str = "Todos",
) -> None:
    st.markdown("### 🏭 Cierres por Sector")

    if CATEGORY_COLUMN not in df_full.columns:
        st.info(f"La columna '{CATEGORY_COLUMN}' no existe en los datos cargados.")
        return

    periods = available_periods(df_full)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"closures_sector_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    sel_year, sel_month = sel
    selected_label = format_period_label(sel_year, sel_month)

    dist = closures_by_sector(df_full, sel_year, sel_month, team)

    if dist.empty:
        st.info(f"No hay cierres en {selected_label} para el equipo {team}.")
        return

    total = int(dist["Total"].sum())
    top = dist.head(15)
    colors = [_COLORS_15[i % len(_COLORS_15)] for i in range(len(top))]

    fig = go.Figure(go.Pie(
        labels=top[CATEGORY_LABEL],
        values=top["Total"],
        hole=0.5,
        marker_colors=colors,
        texttemplate="%{value} (%{percent})",
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
        height=560,
        # Leyenda horizontal debajo (2026-08-14) en vez de columna vertical
        # fija a la derecha — r=180 era el margen fijo más grande de todo
        # el dashboard: en un celular (~340px de ancho útil) dejaba la dona
        # reducida a menos de la mitad del contenedor. Con orientation="h"
        # la leyenda hace wrap sola a cualquier ancho, mismo patrón que
        # `funnel.py`/`trend.py`/`comparison.py`/`leads_summary.py`.
        margin=dict(l=20, r=20, t=20, b=100),
        showlegend=True,
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.12),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Mostrando {total} cierres en {selected_label} para {team}.")
