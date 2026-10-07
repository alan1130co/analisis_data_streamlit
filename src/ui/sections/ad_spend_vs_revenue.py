"""Sección: Gasto en pauta vs Ingresos por redes (barras agrupadas, desde
enero 2025)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    default_anio_index,
    filter_by_anio_mes,
    monthly_ad_spend_with_period,
)
from src.analytics.ad_spend_vs_closures import (
    calculate_redes_revenue_chart,
    combine_ad_spend_and_revenue,
)
from src.config.settings import APP_TIMEZONE

_COLOR_MAP = {
    "Importe": "#1F77B4",        # Azul: gasto
    "Ingreso_Redes": "#FF7F0E",  # Naranja: ingreso
}
_TITLE = "📊 Comparativo Mes-Año: Gasto en pauta vs Ingresos por redes (desde Enero 2025)"


def _anio_actual() -> int:
    return pd.Timestamp.now(tz=APP_TIMEZONE).year


@st.fragment
def render_ad_spend_vs_revenue(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — igual
    que el resto de gráficas históricas de esta pestaña.

    2 selectores independientes: "Año" (`key="anio_ad_spend_vs_revenue"`) y
    "Mes" (`key="mes_ad_spend_vs_revenue"`), ambos default "Todos"
    (respetando el corte "desde enero 2025" que ya aplica
    `combine_ad_spend_and_revenue`). `data` viene en formato largo (una
    fila por "Concepto" — Importe/Ingreso_Redes — por mes), así que las
    opciones del selector "Año" se arman con `.drop_duplicates()` sobre
    "Mes_Año" para no repetir el mismo mes/año dos veces.
    """
    st.markdown(f"### {_TITLE}")

    if gasto_raw is None or gasto_raw.empty:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver el comparativo de gasto en pauta vs "
            "ingresos por redes."
        )
        return

    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_mensual = calculate_redes_revenue_chart(df_clientify)
    data = combine_ad_spend_and_revenue(gasto_mensual, ingreso_mensual)

    if data.empty:
        st.warning(
            "No hay datos de gasto en pauta ni ingresos de redes desde "
            "enero 2025 para mostrar."
        )
        return

    # "Mes_Año" se repite una vez por "Concepto" (formato largo) — dedup
    # antes de armar las opciones del selector.
    meses_disponibles = data["Mes_Año"].drop_duplicates().tolist()
    anios = anios_disponibles(meses_disponibles)
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios,
        index=default_anio_index(anios, _anio_actual()), key="anio_ad_spend_vs_revenue",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_vs_revenue",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    data = data[data["Mes_Año"].isin(labels_permitidos)]

    # El orden ya es cronológico (ver combine_ad_spend_and_revenue) — se
    # toma tal cual como categoryarray porque "Mes_Año" no es ordenable
    # alfabéticamente de forma cronológica.
    orden_meses = data["Mes_Año"].drop_duplicates().tolist()

    fig = px.bar(
        data,
        x="Mes_Año",
        y="Valor",
        color="Concepto",
        barmode="group",
        text="Valor",
        color_discrete_map=_COLOR_MAP,
    )

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden_meses)

    fig.update_traces(
        texttemplate="$%{text:,.2f}",
        textposition="outside",
        cliponaxis=False,
    )

    # Rango del eje Y con margen extra por encima de la barra más alta, para
    # que la etiqueta de valor nunca quede recortada arriba.
    max_y = data["Valor"].max() if not data.empty else 0
    ymax = max_y * 1.25 if max_y > 0 else 1

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Mes y Año",
        xaxis_tickangle=-45,
        bargap=0.25,
        legend_title_text="Concepto",
        yaxis=dict(title="Valor (USD)", tickprefix="$", tickformat=",.0f", range=[0, ymax]),
        showlegend=True,
        margin=dict(t=80),
    )
    st.plotly_chart(fig, use_container_width=True)
