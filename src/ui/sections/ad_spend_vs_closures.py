"""Sección: Gasto en pauta vs cierres con origen en redes (doble eje)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    default_anio_index,
    filter_by_anio_mes,
    monthly_ad_spend,
)
from src.analytics.ad_spend_vs_closures import (
    closures_from_redes_monthly,
    combine_ad_spend_and_closures,
)
from src.config.settings import APP_TIMEZONE
from src.ui.charts import build_stacked_bar_line_figure


def _anio_actual() -> int:
    return pd.Timestamp.now(tz=APP_TIMEZONE).year


@st.fragment
def render_ad_spend_vs_closures(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — esta
    gráfica cruza el histórico completo, igual que la sección de "Cierres
    por canal (Pauta directa vs Referidos)" que la precede en el dashboard.

    2 selectores independientes: "Año" (`key="anio_ad_spend_vs_closures"`) y
    "Mes" (`key="mes_ad_spend_vs_closures"`), ambos default "Todos" —
    filtran ambos traces (barra de gasto y línea de cierres) igual (ver
    `ad_spend.filter_by_anio_mes`, compartida por las 6 gráficas).

    Fix 2026-10-07: barra y línea ahora viven en 2 paneles apilados
    (`src.ui.charts.build_stacked_bar_line_figure`) en vez de compartir
    panel con un eje Y secundario — la línea ya no puede tapar las
    etiquetas de valor de la barra.
    """
    st.markdown("### 📊 Gasto en pauta vs cierres con origen en redes")

    if gasto_raw is None or gasto_raw.empty:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver el cruce entre gasto en pauta y cierres "
            "con origen en redes."
        )
        return

    gasto_mensual = monthly_ad_spend(gasto_raw)
    if gasto_mensual.empty:
        st.warning(
            "El archivo de Meta se cargó pero no se encontraron filas "
            "válidas en USD para calcular el gasto mensual."
        )
        return

    cierres_mensual = closures_from_redes_monthly(df_clientify)
    data = combine_ad_spend_and_closures(gasto_mensual, cierres_mensual)

    meses_disponibles = list(data["Mes_Año"])
    if not meses_disponibles:
        st.info("No hay datos para mostrar.")
        return
    anios = anios_disponibles(meses_disponibles)
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios,
        index=default_anio_index(anios, _anio_actual()), key="anio_ad_spend_vs_closures",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_vs_closures",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    data = data[data["Mes_Año"].isin(labels_permitidos)]

    orden_meses = list(data["Mes_Año"])

    # Rango de cada eje Y con margen extra por encima de su valor más alto,
    # para que la etiqueta de valor nunca quede recortada arriba.
    max_y1 = data["Importe"].max() if not data.empty else 0
    ymax1 = max_y1 * 1.25 if max_y1 > 0 else 1

    max_y2 = data["Cierres_Redes"].max() if not data.empty else 0
    ymax2 = max_y2 * 1.25 if max_y2 > 0 else 1

    bar_traces = [go.Bar(
        x=data["Mes_Año"], y=data["Importe"],
        name="Gasto en pauta (USD)",
        marker_color=px.colors.qualitative.Vivid[0],
        text=[f"${v:,.2f}" for v in data["Importe"]],
        textposition="outside",
    )]
    line_trace = go.Scatter(
        x=data["Mes_Año"], y=data["Cierres_Redes"],
        name="Cierres con origen en redes",
        mode="lines+markers+text",
        marker=dict(color=px.colors.qualitative.Dark2[2], size=8),
        line=dict(width=3),
        text=data["Cierres_Redes"].astype(str),
        textposition="top center",
    )

    fig = build_stacked_bar_line_figure(
        bar_traces, line_trace,
        categoryarray=orden_meses,
        bar_yaxis=dict(title_text="Gasto en pauta (USD)", showgrid=True, range=[0, ymax1]),
        line_yaxis=dict(title_text="Cantidad de cierres (redes)", showgrid=False, range=[0, ymax2]),
    )
    st.plotly_chart(fig, use_container_width=True)
