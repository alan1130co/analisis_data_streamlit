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

_PALETTE = [
    "#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#0891B2",
    "#DC2626", "#D97706", "#059669", "#9333EA", "#E11D48",
    "#94A3B8", "#0EA5E9", "#10B981", "#F59E0B", "#A855F7",
]

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


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
        key="closures_process_type_period",
    )
    sel_year, sel_month = label_to_period[selected_label]

    dist = closures_by_process_type(df_full, sel_year, sel_month, team)

    if dist.empty:
        st.info(f"No hay cierres en {selected_label} para el equipo {team}.")
        return

    dist["Etiqueta"] = dist.apply(
        lambda r: f"{r[CATEGORY_LABEL]} — {int(r['Total'])} cierres ({r['Porcentaje']}%)",
        axis=1,
    )
    total = int(dist["Total"].sum())

    fig = go.Figure(data=[go.Pie(
        labels=dist["Etiqueta"],
        values=dist["Total"],
        hole=0.4,
        sort=False,
        marker=dict(colors=_PALETTE[:len(dist)], line=dict(color="white", width=2)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><extra></extra>",
    )])
    fig.update_layout(
        height=440,
        margin=dict(l=80, r=140, t=20, b=40),
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=11)),
        annotations=[dict(
            text=f"<b>{total}</b><br>Cierres",
            x=0.5, y=0.5, font_size=15, showarrow=False,
        )],
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Mostrando {total} cierres en {selected_label} para {team}.")
