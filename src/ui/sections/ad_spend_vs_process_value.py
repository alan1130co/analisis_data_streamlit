"""Sección: Gasto en pauta vs Valor Total del Proceso (cierres de redes/Pauta).

Ambas magnitudes están en USD (a diferencia de las demás gráficas de esta
pestaña, que cruzan dólares contra cierres/costo por lead) — por eso se
grafican en un único eje Y con barras agrupadas, sin eje secundario.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    filter_by_anio_mes,
    monthly_ad_spend_with_period,
)
from src.analytics.ad_spend_vs_closures import (
    calculate_pauta_process_value_chart,
    combine_ad_spend_and_pauta_process_value,
)

_COLOR_GASTO = "#1F77B4"
_COLOR_VALOR = "#16A34A"


def render_ad_spend_vs_process_value(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — igual
    que el resto de gráficas históricas de esta pestaña.

    2 selectores independientes: "Año" (`key="anio_ad_spend_process_value"`)
    y "Mes" (`key="mes_ad_spend_process_value"`), ambos default "Todos" (ver
    `ad_spend.filter_by_anio_mes`). El DataFrame se filtra ANTES de armar el
    `categoryarray` (mismo patrón que `ad_spend.py`/`ad_spend_vs_closures.py`
    /`ad_spend_cost_per_lead.py`/`ad_spend_vs_revenue.py`), así que el eje X
    ya queda compacto (una sola barra por serie) cuando Año y Mes son ambos
    específicos, sin necesitar el "zoom" de rango que sí requieren
    `ad_spend_roas.py`/`ad_spend_total_roas.py` (esta gráfica no tiene una
    línea de tendencia que deba conservar todos los meses).
    """
    st.markdown("### 📈 Gasto en pauta vs Valor Total del Proceso (cierres de redes)")

    if gasto_raw is None or gasto_raw.empty:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver el comparativo de gasto en pauta vs "
            "valor total del proceso de cierres de Pauta."
        )
        return

    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    valor_mensual = calculate_pauta_process_value_chart(df_clientify)
    data = combine_ad_spend_and_pauta_process_value(gasto_mensual, valor_mensual)

    if data.empty:
        st.warning(
            "No hay datos de gasto en pauta ni de valor de procesos de "
            "Pauta para mostrar."
        )
        return

    meses_disponibles = list(data["Mes_Año"])
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios_disponibles(meses_disponibles),
        index=0, key="anio_ad_spend_process_value",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_process_value",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    data = data[data["Mes_Año"].isin(labels_permitidos)]

    orden_meses = list(data["Mes_Año"])

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=data["Mes_Año"],
        y=data["Importe"],
        name="Gasto en pauta (USD)",
        marker_color=_COLOR_GASTO,
        text=[f"${v:,.0f}" for v in data["Importe"]],
        textposition="outside",
    ))

    fig.add_trace(go.Bar(
        x=data["Mes_Año"],
        y=data["Valor_Proceso_Pauta"],
        name="Valor Total del Proceso (cierres de Pauta) USD",
        marker_color=_COLOR_VALOR,
        text=[f"${v:,.0f}" for v in data["Valor_Proceso_Pauta"]],
        textposition="outside",
    ))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden_meses)
    fig.update_layout(
        template="plotly_white",
        barmode="group",
        xaxis=dict(title="Mes y Año", tickangle=-45),
        yaxis=dict(title="Valor (USD)", tickprefix="$", tickformat=",.0f"),
        legend=dict(x=0.02, y=1.1, orientation="h"),
        bargap=0.25,
        margin=dict(t=80),
    )
    st.plotly_chart(fig, use_container_width=True)
