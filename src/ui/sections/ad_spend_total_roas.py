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
    avoid_label_collision_positions,
    compact_month_xaxis_range,
    default_anio_index,
    filter_by_anio_mes,
    monthly_ad_spend_with_period,
)
from src.analytics.ad_spend_vs_closures import (
    calculate_redes_initial_payments_chart,
    combine_ad_spend_total_revenue_and_roas,
)
from src.config.settings import APP_TIMEZONE

_TITLE = (
    "📊 Gasto total (pauta + honorarios) vs Ingresos por cuota inicial "
    "(redes) y ROAS — desde Enero 2025"
)

_COLOR_GASTO = "#00B5FF"
_COLOR_ING = "#FF2D55"
_COLOR_ROAS = "#34C759"


def _anio_actual() -> int:
    return pd.Timestamp.now(tz=APP_TIMEZONE).year


@st.fragment
def render_ad_spend_total_roas(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame) -> None:
    """`gasto_raw`: reporte de Meta ya cargado/combinado (salida de
    `load_ad_spend_files`, ver `src/ui/sections/ad_spend.py`).
    `df_clientify`: dataset completo de Clientify (df_unfiltered) — igual
    que el resto de gráficas históricas de esta pestaña.

    2 selectores independientes: "Año" (`key="anio_ad_spend_total_roas"`) y
    "Mes" (`key="mes_ad_spend_total_roas"`), ambos default "Todos". Igual
    que en `ad_spend_roas.py`: las 2 barras (Gasto Total, Ingreso) respetan
    la combinación Año/Mes elegida; la línea de ROAS y el eje X ignoran el
    selector de Mes (no tiene sentido un ROAS "puntual" de un solo mes) pero
    SÍ respetan el selector de Año (fix 2026-10-05 — antes usaban siempre
    `df_comb_full` sin filtrar, dejando ver meses de otros años en el eje
    aun con un Año específico elegido). Recortar por Año Y Mes a la vez
    (como las barras) descuadraría el orden de los meses que la línea trae
    (Plotly solo respeta el orden de `categoryarray` para las categorías
    listadas ahí; el resto cae al final, ordenado alfabéticamente) — por eso
    el recorte de la línea/eje es solo por Año.

    Cambio 2026-09-21: cuando Año Y Mes son ambos específicos, se aplica un
    "zoom" al eje (`xaxis.range`, ver `compact_month_xaxis_range`) para que
    la vista quede compacta en esa única barra, sin recortar el
    `categoryarray` (mismo mecanismo que `ad_spend_roas.py`).
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
    anios = anios_disponibles(meses_disponibles)
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios,
        index=default_anio_index(anios, _anio_actual()), key="anio_ad_spend_total_roas",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_total_roas",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    df_barras = df_comb_full[df_comb_full["Mes_Año"].isin(labels_permitidos)]

    # Línea de ROAS y eje X: ignoran el Mes elegido pero SÍ respetan el Año
    # (fix 2026-10-05 — ver docstring).
    labels_roas = filter_by_anio_mes(meses_disponibles, anio_sel, TODOS)
    df_roas_base = df_comb_full[df_comb_full["Mes_Año"].isin(labels_roas)]

    txt_gasto = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Gasto_Total"]]
    txt_ing = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Ingreso_CuotaInicial"]]
    txt_roas = [f"{v:.2f}x" if v > 0 else "" for v in df_roas_base["ROAS"]]

    max_y = max(df_barras["Gasto_Total"].max(), df_barras["Ingreso_CuotaInicial"].max()) if not df_barras.empty else 0
    ymax = max_y * 1.25 if max_y > 0 else 1

    max_roas = df_roas_base["ROAS"].max() if not df_roas_base.empty else 0
    ymax2 = max_roas * 1.25 if max_roas > 0 else 1

    # Posición de la etiqueta de la línea de ROAS: "bottom center" en los
    # meses donde quedaría a una altura de píxel similar a la de CUALQUIERA
    # de las 2 barras agrupadas (Gasto Total, Ingreso) — evita que los
    # números queden encimados (mismo arreglo que `ad_spend_roas.py`).
    bar_categorias_repetidas = pd.concat([df_barras["Mes_Año"], df_barras["Mes_Año"]], ignore_index=True)
    bar_valores_repetidos = pd.concat([df_barras["Gasto_Total"], df_barras["Ingreso_CuotaInicial"]], ignore_index=True)
    line_textposition = avoid_label_collision_positions(
        categories=df_roas_base["Mes_Año"].tolist(),
        values=df_roas_base["ROAS"].tolist(),
        axis_max=ymax2,
        reference_categories=bar_categorias_repetidas.tolist(),
        reference_values=bar_valores_repetidos.tolist(),
        reference_axis_max=ymax,
    )

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
        x=df_roas_base["Mes_Año"],
        y=df_roas_base["ROAS"],
        name="ROAS (Ingreso / Gasto)",
        mode="lines+markers+text",
        marker=dict(color=_COLOR_ROAS, size=9),
        line=dict(width=3),
        text=txt_roas,
        textposition=line_textposition,
        yaxis="y2",
    ))

    categoryarray = df_roas_base["Mes_Año"].tolist()
    xaxis_kwargs = dict(type="category", categoryorder="array", categoryarray=categoryarray)
    xaxis_range = compact_month_xaxis_range(categoryarray, anio_sel, mes_sel)
    if xaxis_range is not None:
        xaxis_kwargs["range"] = xaxis_range
    fig.update_xaxes(**xaxis_kwargs)

    fig.update_layout(
        template="plotly_white",
        barmode="group",
        bargap=0.35,
        bargroupgap=0.15,
        xaxis=dict(title="Mes y Año", tickangle=-45),
        yaxis=dict(title="Valor (USD)", side="left", showgrid=True, range=[0, ymax], tickprefix="$", tickformat=",.0f"),
        yaxis2=dict(title="ROAS (x)", overlaying="y", side="right", showgrid=False, tickformat=".2f", range=[0, ymax2]),
        legend=dict(x=0.02, y=1.15, orientation="h"),
        margin=dict(t=80),
    )
    fig.update_traces(cliponaxis=False)

    st.plotly_chart(fig, use_container_width=True)
