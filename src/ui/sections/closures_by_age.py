from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.closures_by_age import available_periods, closures_by_age

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


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
        key=f"closures_age_period_{default_year}_{default_month}",
    )
    sel_year, sel_month = label_to_period[selected_label]

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
