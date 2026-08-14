"""Sección: Gasto en pauta vs costo promedio por lead de redes (doble eje)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics.ad_spend import monthly_ad_spend
from src.analytics.ad_spend_vs_closures import (
    closures_from_redes_total_monthly,
    combine_ad_spend_and_cost_per_lead,
)


def render_ad_spend_cost_per_lead(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — igual
    que el resto de gráficas históricas de esta pestaña.
    """
    st.markdown("### 💸 Gasto en pauta vs. Costo promedio por lead de redes (Mes-Año)")

    if gasto_raw is None or gasto_raw.empty:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver el costo promedio por lead de redes."
        )
        return

    gasto_mensual = monthly_ad_spend(gasto_raw)
    if gasto_mensual.empty:
        st.warning(
            "El archivo de Meta se cargó pero no se encontraron filas "
            "válidas en USD para calcular el gasto mensual."
        )
        return

    cierres_mensual = closures_from_redes_total_monthly(df_clientify)
    df_comb = combine_ad_spend_and_cost_per_lead(gasto_mensual, cierres_mensual)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_comb["Mes_Año"],
        y=df_comb["Importe"],
        name="Gasto en pauta (USD)",
        marker_color=px.colors.qualitative.Vivid[0],
        text=[f"${v:,.2f}" for v in df_comb["Importe"]],
        textposition="outside",
        yaxis="y1",
    ))

    fig.add_trace(go.Scatter(
        x=df_comb["Mes_Año"],
        y=df_comb["Valor_por_Lead"],
        name="Costo por lead (USD)",
        mode="lines+markers+text",
        marker=dict(color=px.colors.qualitative.Dark2[2], size=8),
        line=dict(width=3),
        text=[f"${v:,.2f}" if v > 0 else "" for v in df_comb["Valor_por_Lead"]],
        textposition="top center",
        yaxis="y2",
    ))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=df_comb["Mes_Año"].tolist())

    fig.update_layout(
        template="plotly_white",
        xaxis=dict(title="Mes y Año", tickangle=-45),
        yaxis=dict(title="Gasto total en pauta (USD)", side="left", showgrid=True, tickprefix="$", tickformat=",.0f"),
        yaxis2=dict(title="Costo promedio por lead (USD)", overlaying="y", side="right", tickprefix="$", tickformat=",.0f"),
        legend=dict(x=0.02, y=1.1, orientation="h"),
        bargap=0.25,
        margin=dict(t=80),
    )
    st.plotly_chart(fig, use_container_width=True)
