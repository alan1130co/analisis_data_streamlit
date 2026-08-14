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
from src.ui.period_selector import format_period_label, render_period_selector


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
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"closures_city_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    sel_year, sel_month = sel
    selected_label = format_period_label(sel_year, sel_month)

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
