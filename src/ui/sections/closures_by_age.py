from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.closures_by_age import available_periods, closures_by_age
from src.ui.period_selector import format_period_label, render_period_selector


def render_closures_by_age(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
    team: str = "Todos",
) -> None:
    st.markdown("### 👥 Cierres por Rango de Edad")

    if "cumpleaños" not in df_full.columns:
        st.info("La columna 'cumpleaños' no existe en los datos cargados.")
        return

    periods = available_periods(df_full)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"closures_age_period_{default_year}_{default_month}",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    sel_year, sel_month = sel
    selected_label = format_period_label(sel_year, sel_month)

    dist = closures_by_age(df_full, sel_year, sel_month, team)

    if dist.empty:
        st.info(f"No hay cierres en {selected_label} para el equipo {team}.")
        return

    total = int(dist["Total"].sum())

    fig = px.bar(
        dist,
        x="Rango de edad",
        y="Total",
        text="Total",
        color="Total",
        color_continuous_scale="Purples",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=20, b=60),
        showlegend=False,
        xaxis_title="Rango de edad",
        yaxis_title="Cierres",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Mostrando {total} cierres en {selected_label} para {team}.")
