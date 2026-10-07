"""Sección: Gasto vs Ingreso por Valor Total del Proceso y ROAS — triple
métrica (barras agrupadas + línea de ROAS en eje secundario, desde enero
2025), mismo formato que `ad_spend_roas.py` ("... por Cuota Inicial y
ROAS") pero usando "Valor total del proceso" como ingreso en vez de la
cuota inicial.

El alcance del ingreso es el MISMO que "Gasto en pauta vs Valor Total del
Proceso (cierres de redes)" (`ad_spend_vs_process_value.py`): reutiliza
`calculate_pauta_process_value_chart` (`ad_spend_vs_closures.py`) — solo
cierres clasificados como Pauta vía `metrics.is_marketing`, NO todos los
cierres del mes — para que ambas gráficas nunca desacuerden sobre qué
cuenta como ingreso de Pauta.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    compact_month_xaxis_range,
    default_anio_index,
    filter_by_anio_mes,
    monthly_ad_spend_with_period,
)
from src.analytics.ad_spend_vs_closures import (
    calculate_pauta_process_value_chart,
    combine_ad_spend_process_value_and_roas,
)
from src.config.settings import APP_TIMEZONE
from src.ui.charts import build_stacked_bar_line_figure

_TITLE = "📈 Comparativo Mes-Año: Gasto vs Ingreso por Valor Total del Proceso y ROAS (desde Enero 2025)"

_COLOR_GASTO = "#00B5FF"
_COLOR_ING = "#16A34A"
_COLOR_ROAS = "#34C759"


def _anio_actual() -> int:
    return pd.Timestamp.now(tz=APP_TIMEZONE).year


@st.fragment
def render_ad_spend_vs_process_value_roas(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — igual
    que el resto de gráficas históricas de esta pestaña.

    2 selectores independientes: "Año" (`key="anio_ad_spend_process_value_
    roas"`) y "Mes" (`key="mes_ad_spend_process_value_roas"`), ambos default
    "Todos" (ver `ad_spend.filter_by_anio_mes`). Mismo patrón que
    `ad_spend_roas.py`/`ad_spend_total_roas.py`: las 2 barras (Gasto,
    Ingreso) respetan la combinación Año/Mes elegida; la línea de ROAS y el
    eje X ignoran el selector de Mes (no tiene sentido un ROAS "puntual" de
    un solo mes) pero SÍ respetan el selector de Año — con Año="Todos" se ve
    el histórico completo (todos los años); con un Año puntual, la línea/eje
    se recortan a los meses de ESE año (sin reintroducir otros años, bug
    corregido 2026-10-05 en las otras 2 gráficas de ROAS de esta pestaña,
    aplicado acá desde el inicio).

    Cuando Año Y Mes son ambos específicos, se aplica el mismo "zoom" de eje
    (`xaxis.range`, ver `compact_month_xaxis_range`) que las otras 2
    gráficas de ROAS.

    Fix 2026-10-07: barras y línea ahora viven en 2 paneles apilados
    (`src.ui.charts.build_stacked_bar_line_figure`) en vez de compartir
    panel con un eje Y secundario — mismo fix que `ad_spend_roas.py`.
    """
    st.markdown(f"### {_TITLE}")

    if gasto_raw is None or gasto_raw.empty:
        st.info(
            "Subí el reporte de Facturación/Inversión de Meta Ads desde el "
            "panel lateral para ver el comparativo de gasto vs ingreso por "
            "valor total del proceso y ROAS."
        )
        return

    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    valor_mensual = calculate_pauta_process_value_chart(df_clientify)
    df_comb_full = combine_ad_spend_process_value_and_roas(gasto_mensual, valor_mensual)

    if df_comb_full.empty:
        st.warning(
            "No hay datos de gasto en pauta ni de valor total del proceso "
            "de cierres de Pauta desde enero 2025 para mostrar."
        )
        return

    meses_disponibles = list(df_comb_full["Mes_Año"])
    anios = anios_disponibles(meses_disponibles)
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios,
        index=default_anio_index(anios, _anio_actual()), key="anio_ad_spend_process_value_roas",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_process_value_roas",
    )

    # Barras: respetan los 2 selectores.
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    df_barras = df_comb_full[df_comb_full["Mes_Año"].isin(labels_permitidos)]

    # Línea de ROAS y eje X: ignoran el Mes elegido pero SÍ respetan el Año.
    labels_roas = filter_by_anio_mes(meses_disponibles, anio_sel, TODOS)
    df_roas_base = df_comb_full[df_comb_full["Mes_Año"].isin(labels_roas)]

    txt_gasto = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Importe"]]
    txt_ing = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Valor_Proceso_Pauta"]]
    txt_roas = [f"{v:.2f}x" if v > 0 else "" for v in df_roas_base["ROAS"]]

    max_y = max(df_barras["Importe"].max(), df_barras["Valor_Proceso_Pauta"].max()) if not df_barras.empty else 0
    ymax = max_y * 1.25 if max_y > 0 else 1

    max_roas = df_roas_base["ROAS"].max() if not df_roas_base.empty else 0
    ymax2 = max_roas * 1.25 if max_roas > 0 else 1

    bar_traces = [
        go.Bar(
            x=df_barras["Mes_Año"], y=df_barras["Importe"],
            name="Gasto en pauta (USD)", marker_color=_COLOR_GASTO,
            text=txt_gasto, textposition="outside", offsetgroup="gasto",
        ),
        go.Bar(
            x=df_barras["Mes_Año"], y=df_barras["Valor_Proceso_Pauta"],
            name="Valor Total del Proceso (USD)", marker_color=_COLOR_ING,
            text=txt_ing, textposition="outside", offsetgroup="ingreso",
        ),
    ]
    line_trace = go.Scatter(
        x=df_roas_base["Mes_Año"], y=df_roas_base["ROAS"],
        name="ROAS (Valor Proceso / Gasto)",
        mode="lines+markers+text",
        marker=dict(color=_COLOR_ROAS, size=9),
        line=dict(width=3),
        text=txt_roas,
        textposition="top center",
    )

    categoryarray = df_roas_base["Mes_Año"].tolist()
    xaxis_range = compact_month_xaxis_range(categoryarray, anio_sel, mes_sel)

    fig = build_stacked_bar_line_figure(
        bar_traces, line_trace,
        categoryarray=categoryarray,
        bar_yaxis=dict(title_text="Valor (USD)", showgrid=True, range=[0, ymax], tickprefix="$", tickformat=",.0f"),
        line_yaxis=dict(title_text="ROAS (Valor Proceso / Gasto)", showgrid=False, tickformat=".2f", range=[0, ymax2]),
        xaxis_range=xaxis_range,
        bargap=0.35,
    )

    st.plotly_chart(fig, use_container_width=True)
