from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.closures_by_gender import (
    closures_by_gender,
    available_periods,
)


_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_COLORES = {
    "Hombre": "#2563EB",
    "Mujer": "#EC4899",
    "No identificado": "#94A3B8",
}

_FILTRO_A_TEAM = {
    "Todos los cierres": "Todos",
    "Solo cierres de pauta": "Marketing (pautas)",
}


def render_closures_by_gender(
    df_full: pd.DataFrame,
    default_year: int,
    default_month: int,
) -> None:
    """Sección: cierres por género del mes, comparativo en bar chart.

    Filtro local (Todos los cierres / Solo cierres de pauta), independiente
    del filtro global de equipo — el usuario pidió control dedicado para
    esta sección específica.
    """

    st.markdown("### 👫 Cierres por género")

    if "nombre" not in df_full.columns:
        st.info("La columna 'nombre' no existe en los datos cargados.")
        return

    periods = available_periods(df_full)
    if not periods:
        st.info("No hay cierres registrados.")
        return

    default = (default_year, default_month) if (default_year, default_month) in periods else periods[0]
    options_labels = [f"{_MONTHS_ES[m]} {y}" for (y, m) in periods]
    label_to_period = dict(zip(options_labels, periods))
    default_label = f"{_MONTHS_ES[default[1]]} {default[0]}"

    col_periodo, col_filtro = st.columns([2, 2])
    with col_periodo:
        selected_label = st.selectbox(
            "Período",
            options=options_labels,
            index=options_labels.index(default_label),
            key=f"closures_gender_period_{default_year}_{default_month}",
        )
    with col_filtro:
        filtro_label = st.radio(
            "Ver",
            options=list(_FILTRO_A_TEAM.keys()),
            index=0,
            key="closures_gender_filtro",
            horizontal=True,
        )
    sel_year, sel_month = label_to_period[selected_label]
    team = _FILTRO_A_TEAM[filtro_label]

    dist = closures_by_gender(df_full, sel_year, sel_month, team)

    if dist.empty:
        st.info(f"No hay cierres en {selected_label} para «{filtro_label}».")
        return

    total = int(dist["Cantidad"].sum())

    fig = px.bar(
        dist,
        x="Género",
        y="Cantidad",
        text="Cantidad",
        color="Género",
        color_discrete_map=_COLORES,
    )
    fig.update_traces(
        textposition="outside",
        textfont=dict(size=14, color="#1F2937"),
    )
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=20, b=40),
        showlegend=False,
        xaxis_title="",
        yaxis_title="Cierres",
        plot_bgcolor="white",
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
    )
    st.plotly_chart(fig, use_container_width=True)

    cols = st.columns(len(dist))
    for i, (_, row) in enumerate(dist.iterrows()):
        with cols[i]:
            st.metric(
                label=row["Género"],
                value=f"{int(row['Cantidad'])} cierres",
                delta=f"{row['Porcentaje']}%",
                delta_color="off",
            )

    st.caption(f"Total {total} cierres en {selected_label} — {filtro_label.lower()}.")
