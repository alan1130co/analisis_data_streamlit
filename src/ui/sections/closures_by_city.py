from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.closures_by_city import (
    CATEGORY_COLUMN,
    CATEGORY_LABEL,
    available_periods,
    closures_by_city,
)

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def render_closures_by_city(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str = "Todos",
) -> None:
    st.markdown("### 🏙️ Cierres por Ciudad")

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
        key="closures_city_period",
    )
    sel_year, sel_month = label_to_period[selected_label]

    dist = closures_by_city(df_full, sel_year, sel_month, team)

    if dist.empty:
        st.info(f"No hay cierres en {selected_label} para el equipo {team}.")
        return

    total = int(dist["Total"].sum())

    fig = px.treemap(
        dist.head(20),
        path=[CATEGORY_LABEL],
        values="Total",
        color="Total",
        color_continuous_scale="Teal",
    )
    fig.update_traces(
        textinfo="label+value+percent root",
        textfont=dict(size=14),
    )
    fig.update_layout(
        height=460,
        margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Mostrando {total} cierres en {selected_label} para {team}.")
