"""Payload de datos agregados para el análisis de IA de la pestaña "Gestión
Comercial" (mismo patrón que los demás `report_payload_*.py`).

4 grupos lógicos:
  1. kpis_del_mes        <- metrics.Metrics (ya calculado en app.py) vs. mes anterior
  2. operacion_diaria    <- daily_sales.daily_sales_total
  3. tendencia_historica <- trend.monthly_trend + leads_summary + closures_vs_second_closures
  4. motivos_no_cierre   <- no_closure.motive_distribution_filtered
"""
from __future__ import annotations

import pandas as pd

from src.analytics.closures_vs_second_closures import closures_vs_second_closures
from src.analytics.daily_sales import daily_sales_total
from src.analytics.leads_summary import leads_summary
from src.analytics.metrics import Metrics
from src.analytics.no_closure import motive_distribution_filtered
from src.analytics.report_payload_common import category_breakdown_payload, daily_series_stats, monthly_series_stats
from src.analytics.trend import monthly_trend

GRUPOS_ORDEN = ["kpis_del_mes", "operacion_diaria", "tendencia_historica", "motivos_no_cierre"]

GRUPOS_TITULOS = {
    "kpis_del_mes": "KPIs del mes vs. mes anterior",
    "operacion_diaria": "Operación diaria (ventas por día)",
    "tendencia_historica": "Tendencia histórica (leads, calificados, cierres)",
    "motivos_no_cierre": "Motivos de no cierre",
}

_KPI_FIELDS = [
    "creados", "calificados", "no_calificados",
    "cierres_marketing", "cierres_referidos",
    "total_cierres_estricto", "eficiencia_real", "eficiencia_global",
]


def _build_kpis_del_mes(metrics: Metrics | None, metrics_prev: Metrics | None) -> dict:
    if metrics is None:
        return {"kpis": {}, "nota": "dato insuficiente — no hay métricas calculadas para este período."}
    actual = metrics.to_dict()
    previo = metrics_prev.to_dict() if metrics_prev is not None else {}
    kpis = {}
    for campo in _KPI_FIELDS:
        valor_actual = actual.get(campo, 0)
        valor_prev = previo.get(campo)
        kpis[campo] = {
            "actual": valor_actual,
            "mes_anterior": valor_prev,
            "variacion": round(valor_actual - valor_prev, 2) if valor_prev is not None else None,
        }
    return {"kpis": kpis}


def _build_operacion_diaria(df: pd.DataFrame, year: int, month: int) -> dict:
    diario = daily_sales_total(df, year, month)
    return {"ventas_diarias": daily_series_stats(diario, "dia", "Cierres")}


def _build_tendencia_historica(df: pd.DataFrame, year: int, month: int) -> dict:
    tendencia = monthly_trend(df, year, month)
    leads_anio = leads_summary(df, year)
    segundos = closures_vs_second_closures(df)

    resultado: dict = {}
    if not tendencia.empty:
        resultado["tendencia_mensual_asignados"] = monthly_series_stats(tendencia, "mes", "Asignados")
        resultado["tendencia_mensual_calificados"] = monthly_series_stats(tendencia, "mes", "Calificados")
        resultado["tendencia_mensual_cierres"] = monthly_series_stats(tendencia, "mes", "Cierres")
    if not leads_anio.empty:
        resultado["leads_mensuales_anio_actual"] = monthly_series_stats(leads_anio, "mes", "Leads")
    if not segundos.empty:
        resultado["cierres_vs_segundos_cierres"] = {
            "cierres": monthly_series_stats(segundos, "Año-Mes", "Cierres"),
            "segundos_cierres": monthly_series_stats(segundos, "Año-Mes", "Segundos cierres"),
        }
    return resultado


def _build_motivos_no_cierre(df: pd.DataFrame, year: int, month: int) -> dict:
    motivos = motive_distribution_filtered(df, year, month)
    return {"motivos": category_breakdown_payload(motivos, "Motivo", "Cantidad")}


def group_payload_builder(group_id: str):
    if group_id == "kpis_del_mes":
        return lambda ctx: _build_kpis_del_mes(ctx.metrics, ctx.metrics_prev)
    if group_id == "operacion_diaria":
        return lambda ctx: _build_operacion_diaria(ctx.df_clientify, ctx.year, ctx.month)
    if group_id == "tendencia_historica":
        return lambda ctx: _build_tendencia_historica(ctx.df_clientify, ctx.year, ctx.month)
    if group_id == "motivos_no_cierre":
        return lambda ctx: _build_motivos_no_cierre(ctx.df_clientify, ctx.year, ctx.month)
    raise KeyError(group_id)


def build_report_payload(
    df: pd.DataFrame,
    year: int,
    month: int,
    metrics: Metrics | None = None,
    metrics_prev: Metrics | None = None,
) -> dict:
    """Payload completo de Gestión Comercial — uso directo (tests, scripts),
    sin pasar por `ReportContext`."""
    df = df if df is not None else pd.DataFrame()
    grupos = {
        "kpis_del_mes": _build_kpis_del_mes(metrics, metrics_prev),
        "operacion_diaria": _build_operacion_diaria(df, year, month),
        "tendencia_historica": _build_tendencia_historica(df, year, month),
        "motivos_no_cierre": _build_motivos_no_cierre(df, year, month),
    }
    return {"periodo": f"{month:02d}/{year}", "grupos": grupos}
