"""Figuras matplotlib para el reporte PDF de "Gestión Comercial" — mismos
datos que `src/ui/kpi_cards.py`/`daily_sales.py`/`trend.py`/
`leads_summary.py`/`closures_vs_second_closures.py`/`no_closure.py`,
agrupados igual que `src/analytics/report_payload_gestion_comercial.py`.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import pandas as pd
from matplotlib.figure import Figure

from src.analytics.closures_vs_second_closures import closures_vs_second_closures
from src.analytics.daily_sales import daily_sales_total
from src.analytics.leads_summary import leads_summary
from src.analytics.metrics import Metrics
from src.analytics.no_closure import motive_distribution_filtered
from src.analytics.trend import monthly_trend
from src.reports.chart_builder_matplotlib_common import (
    grouped_bar_over_categories_figure,
    horizontal_bar_figure,
    multi_line_over_time_figure,
)

CHART_TITLES = {
    "kpis_comparacion": "KPIs del mes vs. mes anterior",
    "ventas_diarias": "Ventas (cierres) diarias del mes",
    "tendencia": "Tendencia mensual (Asignados / Calificados / Cierres)",
    "leads_mensuales": "Leads por mes (año actual)",
    "cierres_vs_segundos": "Cierres vs. segundos cierres por mes",
    "motivos_no_cierre": "Motivos de no cierre",
}

_KPI_FIELDS = ["creados", "calificados", "cierres_marketing", "cierres_referidos", "total_cierres_estricto"]
_KPI_LABELS = {
    "creados": "Creados", "calificados": "Calificados", "cierres_marketing": "Cierres Pauta",
    "cierres_referidos": "Cierres Referidos", "total_cierres_estricto": "Total Cierres",
}


def _build_kpis_comparacion_fig(metrics: Metrics | None, metrics_prev: Metrics | None) -> Figure | None:
    if metrics is None or metrics_prev is None:
        return None
    actual = metrics.to_dict()
    previo = metrics_prev.to_dict()
    tabla = pd.DataFrame({
        "KPI": [_KPI_LABELS[f] for f in _KPI_FIELDS],
        "Mes anterior": [previo.get(f, 0) for f in _KPI_FIELDS],
        "Mes actual": [actual.get(f, 0) for f in _KPI_FIELDS],
    })
    return grouped_bar_over_categories_figure(
        tabla, "KPI",
        [("Mes anterior", "Mes anterior", "#94A3B8"), ("Mes actual", "Mes actual", "#00B5FF")],
        title_y="Cantidad",
    )


def build_figures_by_group_mpl(
    df: pd.DataFrame,
    year: int,
    month: int,
    metrics: Metrics | None,
    metrics_prev: Metrics | None,
) -> dict[str, list[tuple[str, Figure]]]:
    diario = daily_sales_total(df, year, month)
    if not diario.empty:
        diario = diario.assign(dia=diario["dia"].astype(str))
    tendencia = monthly_trend(df, year, month)
    leads_anio = leads_summary(df, year)
    segundos = closures_vs_second_closures(df)
    motivos = motive_distribution_filtered(df, year, month)

    por_grupo = {
        "kpis_del_mes": [
            (CHART_TITLES["kpis_comparacion"], _build_kpis_comparacion_fig(metrics, metrics_prev)),
        ],
        "operacion_diaria": [
            (CHART_TITLES["ventas_diarias"], horizontal_bar_figure(diario, "dia", "Cierres", color="#16A34A", top_n=31)),
        ],
        "tendencia_historica": [
            (CHART_TITLES["tendencia"], multi_line_over_time_figure(
                tendencia, "mes",
                [("Asignados", "Asignados", "#00B5FF"), ("Calificados", "Calificados", "#7C3AED"), ("Cierres", "Cierres", "#16A34A")],
                title_y="Cantidad",
            )),
            (CHART_TITLES["leads_mensuales"], horizontal_bar_figure(leads_anio, "mes", "Leads", color="#F59E0B", top_n=12)),
            (CHART_TITLES["cierres_vs_segundos"], multi_line_over_time_figure(
                segundos, "Año-Mes",
                [("Cierres", "Cierres", "#16A34A"), ("Segundos cierres", "Segundos cierres", "#FF2D55")],
                title_y="Cantidad",
            )),
        ],
        "motivos_no_cierre": [
            (CHART_TITLES["motivos_no_cierre"], horizontal_bar_figure(motivos, "Motivo", "Cantidad", color="#DC2626")),
        ],
    }
    return {
        grupo_id: [(titulo, fig) for titulo, fig in pares if fig is not None]
        for grupo_id, pares in por_grupo.items()
    }
