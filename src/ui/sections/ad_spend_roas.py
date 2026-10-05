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

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    avoid_label_collision_positions,
    compact_month_xaxis_range,
    filter_by_anio_mes,
    monthly_ad_spend_with_period,
)
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

    2 selectores independientes: "Año" (`key="anio_ad_spend_roas"`) y "Mes"
    (`key="mes_ad_spend_roas"`), ambos default "Todos" (ver
    `ad_spend.filter_by_anio_mes`, compartida por las 6 gráficas). A
    diferencia de las otras gráficas de esta pestaña, acá el filtro NO
    aplica parejo a los 3 traces: las 2 barras (Gasto, Ingreso) sí se
    restringen a la combinación Año/Mes elegida, pero la línea de ROAS (y el
    eje X) ignoran el selector de Mes a propósito — el ROAS es una métrica
    de tendencia, no tiene sentido "puntual" para un solo mes aislado.

    Fix 2026-10-05 (antes usaban siempre `df_comb_full` sin filtrar): con
    Año="Todos" la línea de ROAS/eje X siguen mostrando el histórico
    COMPLETO (todos los años) — comportamiento confirmado, sin cambios. Pero
    con un Año puntual elegido, la línea de ROAS/eje X ahora se recortan a
    los meses de ESE año (`filter_by_anio_mes(..., anio_sel, TODOS)` —
    ignora el Mes elegido, solo el Año) — antes, elegir Año=2025 igual
    dejaba ver en el eje/la línea los meses de 2026 (y cualquier otro año),
    porque la línea nunca se filtraba por año. El eje X se arma con esa
    misma lista recortada (no la lista completa sin filtrar): si se
    recortara por Año Y Mes a la vez (como las barras), Plotly igual
    dibujaría los demás meses del Año elegido en el eje (los traces
    comparten eje X) pero desordenados — Plotly solo respeta el orden de
    `categoryarray` para las categorías que están ahí listadas, y manda al
    final, ordenadas alfabéticamente, las que faltan. Recortar solo por Año
    (no por Mes) evita ese descuadre sin reintroducir años que el usuario ya
    excluyó.

    Cambio 2026-09-21: cuando Año Y Mes son ambos específicos (un único mes
    puntual), se aplica un "zoom" al eje (`xaxis.range`, ver
    `compact_month_xaxis_range`) para que la vista quede compacta en esa
    única barra — el `categoryarray` en sí NO se recorta más allá del Año
    (sigue incluyendo todos los meses de ese año, mismo orden de siempre),
    solo se ajusta la ventana visible. Si Año o Mes quedan en "Todos", no se
    aplica rango — eje completo (o del año elegido), sin cambios.
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
    df_comb_full = combine_ad_spend_revenue_and_roas(gasto_mensual, ingreso_mensual)

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
        index=0, key="anio_ad_spend_roas",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_roas",
    )
    # Barras: respetan los 2 selectores.
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    df_barras = df_comb_full[df_comb_full["Mes_Año"].isin(labels_permitidos)]

    # Línea de ROAS y eje X: ignoran el selector de Mes (ver docstring — el
    # ROAS es una tendencia, no un valor puntual), pero SÍ respetan el
    # selector de Año (fix 2026-10-05: antes usaban siempre df_comb_full sin
    # filtrar, dejando ver meses de otros años aun con un Año específico
    # elegido).
    labels_roas = filter_by_anio_mes(meses_disponibles, anio_sel, TODOS)
    df_roas_base = df_comb_full[df_comb_full["Mes_Año"].isin(labels_roas)]

    txt_gasto = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Importe"]]
    txt_ing = [f"${v:,.0f}" if v > 0 else "" for v in df_barras["Ingreso_CuotaInicial"]]
    txt_roas = [f"{v:.2f}x" if v > 0 else "" for v in df_roas_base["ROAS"]]

    max_y = max(df_barras["Importe"].max(), df_barras["Ingreso_CuotaInicial"].max()) if not df_barras.empty else 0
    ymax = max_y * 1.25 if max_y > 0 else 1

    max_roas = df_roas_base["ROAS"].max() if not df_roas_base.empty else 0
    ymax2 = max_roas * 1.25 if max_roas > 0 else 1

    # Posición de la etiqueta de la línea de ROAS: "bottom center" en vez de
    # "top center" en los meses donde quedaría a una altura de píxel similar
    # a la de CUALQUIERA de las 2 barras agrupadas de ese mismo mes (Gasto,
    # Ingreso) — evita que los números queden encimados e ilegibles. Los
    # meses donde la línea trae datos pero no hay barra visible (Mes
    # específico elegido, ver docstring) no tienen con qué chocar -> queda
    # en "top center" (sin cambios).
    bar_categorias_repetidas = pd.concat([df_barras["Mes_Año"], df_barras["Mes_Año"]], ignore_index=True)
    bar_valores_repetidos = pd.concat([df_barras["Importe"], df_barras["Ingreso_CuotaInicial"]], ignore_index=True)
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
        y=df_barras["Importe"],
        name="Gasto en pauta (USD)",
        marker_color=_COLOR_GASTO,
        text=txt_gasto,
        textposition="outside",
        offsetgroup="gasto",
    ))

    fig.add_trace(go.Bar(
        x=df_barras["Mes_Año"],
        y=df_barras["Ingreso_CuotaInicial"],
        name="Ingresos por cuota inicial (USD)",
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
        yaxis2=dict(title="ROAS (Ingreso / Gasto)", overlaying="y", side="right", showgrid=False, tickformat=".2f", range=[0, ymax2]),
        legend=dict(x=0.02, y=1.15, orientation="h"),
        margin=dict(t=80),
    )
    fig.update_traces(cliponaxis=False)

    st.plotly_chart(fig, use_container_width=True)
