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
    filter_by_anio_mes,
    monthly_ad_spend,
)
from src.analytics.ad_spend_vs_closures import (
    closures_from_redes_monthly,
    combine_ad_spend_and_closures,
)


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
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios_disponibles(meses_disponibles),
        index=0, key="anio_ad_spend_vs_closures",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_vs_closures",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    data = data[data["Mes_Año"].isin(labels_permitidos)]

    orden_meses = list(data["Mes_Año"])

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=data["Mes_Año"],
        y=data["Importe"],
        name="Gasto en pauta (USD)",
        marker_color=px.colors.qualitative.Vivid[0],
        text=[f"${v:,.2f}" for v in data["Importe"]],
        textposition="outside",
        yaxis="y1",
    ))

    fig.add_trace(go.Scatter(
        x=data["Mes_Año"],
        y=data["Cierres_Redes"],
        name="Cierres con origen en redes",
        mode="lines+markers+text",
        marker=dict(color=px.colors.qualitative.Dark2[2], size=8),
        line=dict(width=3),
        text=data["Cierres_Redes"].astype(str),
        textposition="top center",
        yaxis="y2",
    ))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden_meses)
    fig.update_layout(
        template="plotly_white",
        xaxis=dict(title="Mes y Año", tickangle=-45),
        yaxis=dict(title="Gasto en pauta (USD)", side="left", showgrid=True),
        yaxis2=dict(title="Cantidad de cierres (redes)", overlaying="y", side="right", showgrid=False),
        legend=dict(x=0.02, y=1.1, orientation="h"),
        bargap=0.25,
        margin=dict(t=80),
    )
    st.plotly_chart(fig, use_container_width=True)
