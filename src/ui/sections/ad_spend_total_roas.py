"""Sección: Gasto total (pauta + honorarios) vs Ingresos por cuota inicial
de redes y ROAS — variante más completa de `ad_spend_roas.py` que incorpora
el honorario fijo mensual del equipo (`HONORARIOS_EQUIPO_MARKETING_USD`,
~$3,485.44 USD) al costo operativo total, pero solo desde julio 2026 en
adelante (`HONORARIOS_EQUIPO_DESDE_ANIO`/`_MES` en settings.py) — meses
previos muestran gasto en pauta puro, sin honorarios."""
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
    calculate_redes_initial_payments_chart,
    combine_ad_spend_total_revenue_and_roas,
)

_TITLE = (
    "📊 Gasto total (pauta + honorarios) vs Ingresos por cuota inicial "
    "(redes) y ROAS — desde Enero 2025"
)

_COLOR_GASTO = "#00B5FF"
_COLOR_ING = "#FF2D55"
_COLOR_ROAS = "#34C759"


def render_ad_spend_total_roas(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — igual
    que el resto de gráficas históricas de esta pestaña.

    2 selectores independientes: "Año" (`key="anio_ad_spend_total_roas"`) y
    "Mes" (`key="mes_ad_spend_total_roas"`), ambos default "Todos". Igual
    que en `ad_spend_roas.py`: las 2 barras (Gasto Total, Ingreso) respetan
    la combinación Año/Mes elegida, pero la línea de ROAS y el eje X
    SIEMPRE usan `df_comb_full` (todos los meses desde enero 2025) —
    recortar el eje junto con las barras descuadraría el orden de los
    meses que la línea sigue trayendo (Plotly solo respeta el orden de
    `categoryarray` para las categorías listadas ahí; el resto cae al
    final, ordenado alfabéticamente).
    """
    st.markdown(f"### {_TITLE}")

    if gasto_raw is None or gasto_raw.empty:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver el comparativo de gasto total (pauta + "
            "honorarios) vs ingreso por cuota inicial y ROAS."
        )
        return

    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_mensual = calculate_redes_initial_payments_chart(df_clientify)
    df_comb_full = combine_ad_spend_total_revenue_and_roas(gasto_mensual, ingreso_mensual)

    if df_comb_full.empty:
        st.warning(
            "No hay datos de gasto en pauta ni ingresos por cuota inicial "
            "desde enero 2025 para mostrar."
        )
        return

    meses_disponibles = list(df_comb_full["Mes_Año"])
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios_disponibles(meses_disponibles),
        index=0, key="anio_ad_spend_total_roas",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_total_roas",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    df_barras = df_comb_full[df_comb_full["Mes_Año"].isin(labels_permitidos)]

    txt_gasto = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Gasto_Total"]]
    txt_ing = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Ingreso_CuotaInicial"]]
    txt_roas = [f"{v:.2f}x" if v > 0 else "" for v in df_comb_full["ROAS"]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_barras["Mes_Año"],
        y=df_barras["Gasto_Total"],
        name="Gasto total (pauta + honorarios) USD",
        marker_color=_COLOR_GASTO,
        text=txt_gasto,
        textposition="outside",
        offsetgroup="gasto",
    ))

    fig.add_trace(go.Bar(
        x=df_barras["Mes_Año"],
        y=df_barras["Ingreso_CuotaInicial"],
        name="Ingresos por cuota inicial (redes) USD",
        marker_color=_COLOR_ING,
        text=txt_ing,
        textposition="outside",
        offsetgroup="ingreso",
    ))

    fig.add_trace(go.Scatter(
        x=df_comb_full["Mes_Año"],
        y=df_comb_full["ROAS"],
        name="ROAS (Ingreso / Gasto)",
        mode="lines+markers+text",
        marker=dict(color=_COLOR_ROAS, size=9),
        line=dict(width=3),
        text=txt_roas,
        textposition="top center",
        yaxis="y2",
    ))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=df_comb_full["Mes_Año"].tolist())

    max_y = max(df_barras["Gasto_Total"].max(), df_barras["Ingreso_CuotaInicial"].max())
    ymax = max_y * 1.25 if max_y > 0 else 1

    fig.update_layout(
        template="plotly_white",
        barmode="group",
        bargap=0.35,
        bargroupgap=0.15,
        xaxis=dict(title="Mes y Año", tickangle=-45),
        yaxis=dict(title="Valor (USD)", side="left", showgrid=True, range=[0, ymax], tickprefix="$", tickformat=",.0f"),
        yaxis2=dict(title="ROAS (x)", overlaying="y", side="right", showgrid=False, tickformat=".2f"),
        legend=dict(x=0.02, y=1.15, orientation="h"),
        margin=dict(t=80),
    )
    fig.update_traces(cliponaxis=False)

    st.plotly_chart(fig, use_container_width=True)
