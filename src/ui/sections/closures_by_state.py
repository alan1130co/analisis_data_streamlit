from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.closures_by_state import (
    CATEGORY_COLUMN,
    CATEGORY_LABEL,
    available_periods,
    closures_by_state,
)
from src.ui.period_selector import format_period_label, render_period_selector


def render_closures_by_state(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str = "Todos",
) -> None:
    st.markdown("### 🗺️ Cierres por Estado/Provincia")

    if CATEGORY_COLUMN not in df_full.columns:
        st.info(f"La columna '{CATEGORY_COLUMN}' no existe en los datos cargados.")
        return

    periods = available_periods(df_full)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"closures_state_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    sel_year, sel_month = sel
    selected_label = format_period_label(sel_year, sel_month)

    dist = closures_by_state(df_full, sel_year, sel_month, team)

    if dist.empty:
        st.info(f"No hay cierres en {selected_label} para el equipo {team}.")
        return

    total = int(dist["Total"].sum())

    fig = px.bar(
        dist.head(15),
        x="Total",
        y=CATEGORY_LABEL,
        orientation="h",
        text="Total",
        color="Total",
        color_continuous_scale="Blues",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=max(360, 30 * len(dist.head(15))),
        margin=dict(l=20, r=80, t=20, b=20),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        xaxis_title="Cierres",
        yaxis_title="",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Mostrando {total} cierres en {selected_label} para {team}.")
