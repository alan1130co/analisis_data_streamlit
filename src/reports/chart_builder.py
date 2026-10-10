"""Construye las 9 figuras de Plotly de "Marketing e Inversión" para el
reporte PDF (`src/reports/pdf_report.py`) — mismas fuentes/combinaciones de
datos que `src/analytics/report_payload.py` (y que los 9 `render_*` de
`src/ui/sections/ad_spend*.py`), pero sin selector de Mes: el reporte solo
filtra por Año (o "Todos"), no por un mes puntual.

Reutiliza `build_stacked_bar_line_figure` de `src/ui/charts.py` (constructor
de figura puro, sin llamadas a `st.*`) para que el estilo de las gráficas
barra+línea sea idéntico al de la app interactiva.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.analytics.ad_spend import (
    TODOS,
    combine_real_vs_billed_monthly,
    monthly_ad_spend,
    monthly_ad_spend_with_period,
    parse_mes_anio,
)
from src.analytics.ad_spend_vs_closures import (
    calculate_pauta_process_value_chart,
    calculate_redes_initial_payments_chart,
    calculate_redes_revenue_chart,
    closures_from_redes_monthly,
    closures_from_redes_total_monthly,
    combine_ad_spend_and_closures,
    combine_ad_spend_and_cost_per_lead,
    combine_ad_spend_and_pauta_process_value,
    combine_ad_spend_and_revenue,
    combine_ad_spend_process_value_and_roas,
    combine_ad_spend_revenue_and_roas,
    combine_ad_spend_total_revenue_and_roas,
)
from src.ui.charts import build_stacked_bar_line_figure

_COLOR_GASTO = "#00B5FF"
_COLOR_ING = "#FF2D55"
_COLOR_ROAS = "#34C759"
_COLOR_FACTURADO = "#F59E0B"
_COLOR_VALOR = "#16A34A"

CHART_TITLES = {
    "gasto_real": "Gasto en pauta publicitaria (Meta Ads)",
    "gasto_facturado": "Gasto facturado por mes (cobros de Meta)",
    "gasto_vs_ingresos_redes": "Gasto en pauta vs Ingresos por redes",
    "roas_pauta": "Gasto vs Ingreso por Cuota Inicial y ROAS",
    "costo_por_lead": "Gasto en pauta vs Costo promedio por lead de redes",
    "roas_total": "Gasto total (pauta + honorarios) vs Ingresos y ROAS",
    "cierres_vs_gasto": "Gasto en pauta vs cierres con origen en redes",
    "gasto_vs_valor_proceso": "Gasto en pauta vs Valor Total del Proceso",
    "gasto_vs_valor_proceso_roas": "Gasto vs Ingreso por Valor Total del Proceso y ROAS",
}


def _filter_anio(df: pd.DataFrame, anio: int | str) -> pd.DataFrame:
    if df.empty or anio == TODOS:
        return df
    if "Año" in df.columns:
        return df[df["Año"] == anio].reset_index(drop=True)
    anios = df["Mes_Año"].apply(lambda label: parse_mes_anio(label)[0])
    return df[anios == anio].reset_index(drop=True)


def _bars_figure(df: pd.DataFrame, bar_specs: list[tuple[str, str, str]], yaxis_title: str) -> go.Figure | None:
    if df.empty:
        return None
    orden = df["Mes_Año"].drop_duplicates().tolist()
    fig = go.Figure()
    max_y = 0.0
    for value_col, name, color in bar_specs:
        if value_col not in df.columns:
            continue
        max_y = max(max_y, float(df[value_col].max()))
        fig.add_trace(go.Bar(
            x=df["Mes_Año"], y=df[value_col], name=name, marker_color=color,
            text=[f"${v:,.0f}" for v in df[value_col]], textposition="outside",
        ))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden, tickangle=-45)
    ymax = max_y * 1.25 if max_y > 0 else 1
    fig.update_yaxes(title="Valor (USD)" if yaxis_title is None else yaxis_title, tickprefix="$", tickformat=",.0f", range=[0, ymax])
    fig.update_layout(
        template="plotly_white", barmode="group", bargap=0.25,
        margin=dict(t=60, b=80), legend=dict(orientation="h", y=1.15),
        showlegend=len(bar_specs) > 1,
    )
    fig.update_traces(cliponaxis=False)
    return fig


def _bars_and_line_figure(
    df: pd.DataFrame,
    bar_specs: list[tuple[str, str, str]],
    line_spec: tuple[str, str, str, str],
    bar_yaxis_title: str,
    line_yaxis_title: str,
    money_bars: bool = True,
) -> go.Figure | None:
    if df.empty:
        return None
    orden = df["Mes_Año"].drop_duplicates().tolist()

    bar_traces = []
    max_bar = 0.0
    for value_col, name, color in bar_specs:
        max_bar = max(max_bar, float(df[value_col].max()))
        text = [f"${v:,.0f}" if money_bars else f"{v:,.0f}" for v in df[value_col]]
        bar_traces.append(go.Bar(
            x=df["Mes_Año"], y=df[value_col], name=name, marker_color=color,
            text=text, textposition="outside",
        ))

    line_col, line_name, line_color, line_fmt = line_spec
    max_line = float(df[line_col].max())
    line_trace = go.Scatter(
        x=df["Mes_Año"], y=df[line_col], name=line_name, mode="lines+markers+text",
        marker=dict(color=line_color, size=8), line=dict(width=3),
        text=[line_fmt.format(v) if v else "" for v in df[line_col]],
        textposition="top center",
    )

    bar_yaxis = dict(title_text=bar_yaxis_title, showgrid=True, range=[0, max_bar * 1.25 if max_bar > 0 else 1])
    if money_bars:
        bar_yaxis.update(tickprefix="$", tickformat=",.0f")
    line_yaxis = dict(title_text=line_yaxis_title, showgrid=False, range=[0, max_line * 1.25 if max_line > 0 else 1])

    return build_stacked_bar_line_figure(
        bar_traces, line_trace, categoryarray=orden, bar_yaxis=bar_yaxis, line_yaxis=line_yaxis,
    )


def _df_gasto_real(gasto_raw: pd.DataFrame, anio) -> pd.DataFrame:
    return _filter_anio(monthly_ad_spend_with_period(gasto_raw), anio)


def _df_gasto_facturado(billed_raw: pd.DataFrame | None, anio) -> pd.DataFrame:
    if billed_raw is None or billed_raw.empty:
        return pd.DataFrame()
    return _filter_anio(monthly_ad_spend_with_period(billed_raw), anio)


def _df_gasto_vs_ingresos_redes(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> pd.DataFrame:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_mensual = calculate_redes_revenue_chart(df_clientify)
    largo = combine_ad_spend_and_revenue(gasto_mensual, ingreso_mensual)
    if largo.empty:
        return largo
    ancho = largo.pivot(index=["Año", "Mes_num", "Mes_Año"], columns="Concepto", values="Valor").reset_index()
    return _filter_anio(ancho.sort_values(["Año", "Mes_num"]), anio)


def _df_roas_pauta(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> pd.DataFrame:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_mensual = calculate_redes_initial_payments_chart(df_clientify)
    return _filter_anio(combine_ad_spend_revenue_and_roas(gasto_mensual, ingreso_mensual), anio)


def _df_costo_por_lead(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> pd.DataFrame:
    gasto_mensual = monthly_ad_spend(gasto_raw)
    cierres_mensual = closures_from_redes_total_monthly(df_clientify)
    return _filter_anio(combine_ad_spend_and_cost_per_lead(gasto_mensual, cierres_mensual), anio)


def _df_roas_total(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> pd.DataFrame:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_mensual = calculate_redes_initial_payments_chart(df_clientify)
    return _filter_anio(combine_ad_spend_total_revenue_and_roas(gasto_mensual, ingreso_mensual), anio)


def _df_cierres_vs_gasto(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> pd.DataFrame:
    gasto_mensual = monthly_ad_spend(gasto_raw)
    cierres_mensual = closures_from_redes_monthly(df_clientify)
    return _filter_anio(combine_ad_spend_and_closures(gasto_mensual, cierres_mensual), anio)


def _df_gasto_vs_valor_proceso(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> pd.DataFrame:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    valor_mensual = calculate_pauta_process_value_chart(df_clientify)
    return _filter_anio(combine_ad_spend_and_pauta_process_value(gasto_mensual, valor_mensual), anio)


def _df_gasto_vs_valor_proceso_roas(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> pd.DataFrame:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    valor_mensual = calculate_pauta_process_value_chart(df_clientify)
    return _filter_anio(combine_ad_spend_process_value_and_roas(gasto_mensual, valor_mensual), anio)


def build_gasto_real(gasto_raw: pd.DataFrame, anio) -> go.Figure | None:
    df = _df_gasto_real(gasto_raw, anio)
    return _bars_figure(df, [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO)], "Gasto en pauta (USD)")


def build_gasto_facturado(billed_raw: pd.DataFrame | None, anio) -> go.Figure | None:
    df = _df_gasto_facturado(billed_raw, anio)
    if df.empty:
        return None
    return _bars_figure(df, [("Importe", "Facturado (USD)", _COLOR_FACTURADO)], "Total facturado (USD)")


def build_gasto_vs_ingresos_redes(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> go.Figure | None:
    ancho = _df_gasto_vs_ingresos_redes(gasto_raw, df_clientify, anio)
    if ancho.empty:
        return None
    return _bars_figure(
        ancho,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Ingreso_Redes", "Ingresos por redes (USD)", "#FF7F0E")],
        "Valor (USD)",
    )


def build_roas_pauta(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> go.Figure | None:
    df = _df_roas_pauta(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Ingreso_CuotaInicial", "Ingreso por cuota inicial (USD)", _COLOR_ING)],
        ("ROAS", "ROAS (Ingreso / Gasto)", _COLOR_ROAS, "{:.2f}x"),
        "Valor (USD)", "ROAS (x)",
    )


def build_costo_por_lead(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> go.Figure | None:
    df = _df_costo_por_lead(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO)],
        ("Valor_por_Lead", "Costo por lead (USD)", "#117A65", "${:.2f}"),
        "Gasto en pauta (USD)", "Costo por lead (USD)",
    )


def build_roas_total(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> go.Figure | None:
    df = _df_roas_total(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure(
        df,
        [("Gasto_Total", "Gasto total (pauta + honorarios) USD", _COLOR_GASTO), ("Ingreso_CuotaInicial", "Ingreso por cuota inicial (USD)", _COLOR_ING)],
        ("ROAS", "ROAS (Ingreso / Gasto)", _COLOR_ROAS, "{:.2f}x"),
        "Valor (USD)", "ROAS (x)",
    )


def build_cierres_vs_gasto(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> go.Figure | None:
    df = _df_cierres_vs_gasto(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO)],
        ("Cierres_Redes", "Cierres con origen en redes", "#117A65", "{:.0f}"),
        "Gasto en pauta (USD)", "Cantidad de cierres (redes)",
        money_bars=True,
    )


def build_gasto_vs_valor_proceso(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> go.Figure | None:
    df = _df_gasto_vs_valor_proceso(gasto_raw, df_clientify, anio)
    return _bars_figure(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Valor_Proceso_Pauta", "Valor Total del Proceso (USD)", _COLOR_VALOR)],
        "Valor (USD)",
    )


def build_gasto_vs_valor_proceso_roas(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> go.Figure | None:
    df = _df_gasto_vs_valor_proceso_roas(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Valor_Proceso_Pauta", "Valor Total del Proceso (USD)", _COLOR_ING)],
        ("ROAS", "ROAS (Valor Proceso / Gasto)", _COLOR_ROAS, "{:.2f}x"),
        "Valor (USD)", "ROAS (x)",
    )


def build_figures_by_group(
    gasto_raw: pd.DataFrame,
    df_clientify: pd.DataFrame,
    billed_raw: pd.DataFrame | None,
    anio,
) -> dict[str, list[tuple[str, go.Figure]]]:
    """Mapea cada grupo lógico (ver `src/analytics/report_payload.py`) a su
    lista de `(título, figura)` — figuras `None` (sin datos) ya vienen
    filtradas, no se incluyen en el resultado."""
    por_grupo = {
        "gasto_y_facturado": [
            (CHART_TITLES["gasto_real"], build_gasto_real(gasto_raw, anio)),
            (CHART_TITLES["gasto_facturado"], build_gasto_facturado(billed_raw, anio)),
        ],
        "gasto_vs_ingresos_y_roas": [
            (CHART_TITLES["gasto_vs_ingresos_redes"], build_gasto_vs_ingresos_redes(gasto_raw, df_clientify, anio)),
            (CHART_TITLES["roas_pauta"], build_roas_pauta(gasto_raw, df_clientify, anio)),
        ],
        "costo_por_lead": [
            (CHART_TITLES["costo_por_lead"], build_costo_por_lead(gasto_raw, df_clientify, anio)),
        ],
        "roas_total": [
            (CHART_TITLES["roas_total"], build_roas_total(gasto_raw, df_clientify, anio)),
        ],
        "cierres_y_valor_proceso": [
            (CHART_TITLES["cierres_vs_gasto"], build_cierres_vs_gasto(gasto_raw, df_clientify, anio)),
            (CHART_TITLES["gasto_vs_valor_proceso"], build_gasto_vs_valor_proceso(gasto_raw, df_clientify, anio)),
            (CHART_TITLES["gasto_vs_valor_proceso_roas"], build_gasto_vs_valor_proceso_roas(gasto_raw, df_clientify, anio)),
        ],
    }
    return {
        grupo_id: [(titulo, fig) for titulo, fig in pares if fig is not None]
        for grupo_id, pares in por_grupo.items()
    }
