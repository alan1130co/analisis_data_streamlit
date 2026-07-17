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

_TRANSPARENT = "rgba(0,0,0,0)"
_COLORS_15 = [
    "#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#0891B2",
    "#DC2626", "#D97706", "#059669", "#9333EA", "#E11D48",
    "#0EA5E9", "#65A30D", "#DB2777", "#4F46E5", "#EAB308",
]

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


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
    if not periods:
        st.info("No hay cierres registrados.")
        return

    default = (default_year, default_month) if (default_year, default_month) in periods else periods[0]
    options_labels = [f"{_MONTHS_ES[m]} {y}" for (y, m) in periods]
    label_to_period = dict(zip(options_labels, periods))
    default_label = f"{_MONTHS_ES[default[1]]} {default[0]}"

    selected_label = st.selectbox(
        "Período",
        options=options_labels,
        index=options_labels.index(default_label),
        key=f"closures_sector_period_{default_year}_{default_month}",
    )
    sel_year, sel_month = label_to_period[selected_label]

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
        height=460,
        margin=dict(l=20, r=180, t=20, b=20),
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5, xanchor="left", yanchor="middle"),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Mostrando {total} cierres en {selected_label} para {team}.")
