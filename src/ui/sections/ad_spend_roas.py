"""Sección: Gasto en pauta vs Ingresos por cuota inicial y ROAS — triple
métrica (barras agrupadas + línea de ROAS en eje secundario, desde enero
2025).

Desde 2026-08-13h usa la lógica aislada `calculate_redes_initial_payments_
chart` para el ingreso (cuota inicial correcta por cada una de las 4 etapas
de cierre, cruzada con la máscara de canales de redes).

REVERTIDO 2026-08-13k: el "Gasto" de ESTA gráfica es PURO gasto en pauta
(Meta Ads) — NO incluye honorarios ni sueldos del equipo. Esto la deja
independiente de `ad_spend_total_roas.py` (que SÍ suma honorarios, por
defecto $2,000/mes vía `HONORARIOS_FIJOS_MENSUALES_USD`) y de la versión
intermedia 2026-08-13i de este mismo archivo (que sumaba
`HONORARIOS_EQUIPO_MARKETING_USD` aquí también — ya no)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.ad_spend import monthly_ad_spend_with_period
from src.analytics.ad_spend_vs_closures import (
    calculate_redes_initial_payments_chart,
    combine_ad_spend_revenue_and_roas,
)

_TITLE = "💹 Comparativo Mes-Año: Gasto vs Ingreso por Cuota Inicial y ROAS (desde Enero 2025)"

_COLOR_GASTO = "#00B5FF"
_COLOR_ING = "#FF2D55"
_COLOR_ROAS = "#34C759"


def render_ad_spend_roas(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — igual
    que el resto de gráficas históricas de esta pestaña.
    """
    st.markdown(f"### {_TITLE}")

    if gasto_raw is None or gasto_raw.empty:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver el comparativo de gasto vs ingreso por "
            "cuota inicial y ROAS."
        )
        return

    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_mensual = calculate_redes_initial_payments_chart(df_clientify)
    df_comb = combine_ad_spend_revenue_and_roas(gasto_mensual, ingreso_mensual)

    if df_comb.empty:
        st.warning(
            "No hay datos de gasto en pauta ni ingresos por cuota inicial "
            "desde enero 2025 para mostrar."
        )
        return

    txt_gasto = [f"${v:,.0f}" if v > 0 else "" for v in df_comb["Importe"]]
    txt_ing = [f"${v:,.0f}" if v > 0 else "" for v in df_comb["Ingreso_CuotaInicial"]]
    txt_roas = [f"{v:.2f}x" if v > 0 else "" for v in df_comb["ROAS"]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_comb["Mes_Año"],
        y=df_comb["Importe"],
        name="Gasto en pauta (USD)",
        marker_color=_COLOR_GASTO,
        text=txt_gasto,
        textposition="outside",
        offsetgroup="gasto",
    ))

    fig.add_trace(go.Bar(
        x=df_comb["Mes_Año"],
        y=df_comb["Ingreso_CuotaInicial"],
        name="Ingresos por cuota inicial (USD)",
        marker_color=_COLOR_ING,
        text=txt_ing,
        textposition="outside",
        offsetgroup="ingreso",
    ))

    fig.add_trace(go.Scatter(
        x=df_comb["Mes_Año"],
        y=df_comb["ROAS"],
        name="ROAS (Ingreso / Gasto)",
        mode="lines+markers+text",
        marker=dict(color=_COLOR_ROAS, size=9),
        line=dict(width=3),
        text=txt_roas,
        textposition="top center",
        yaxis="y2",
    ))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=df_comb["Mes_Año"].tolist())

    max_y = max(df_comb["Importe"].max(), df_comb["Ingreso_CuotaInicial"].max())
    ymax = max_y * 1.25 if max_y > 0 else 1

    fig.update_layout(
        template="plotly_white",
        barmode="group",
        bargap=0.35,
        bargroupgap=0.15,
        xaxis=dict(title="Mes y Año", tickangle=-45),
        yaxis=dict(title="Valor (USD)", side="left", showgrid=True, range=[0, ymax], tickprefix="$", tickformat=",.0f"),
        yaxis2=dict(title="ROAS (Ingreso / Gasto)", overlaying="y", side="right", showgrid=False, tickformat=".2f"),
        legend=dict(x=0.02, y=1.15, orientation="h"),
        margin=dict(t=80),
    )
    fig.update_traces(cliponaxis=False)

    st.plotly_chart(fig, use_container_width=True)
