"""Payload de datos agregados para el análisis de IA de la pestaña "Embudo
y Canales" (mismo patrón que `report_payload.py`/`report_payload_
segmentacion.py` — ver esos módulos para la regla de oro de "sin PII, sin
aritmética de la IA").

4 grupos lógicos:
  1. embudo_por_asesor   <- funnel.funnel_by_advisor (tabla por ASESOR —
                            nombre de empleado, no de cliente, no es PII de
                            contacto de Clientify)
  2. pauta_vs_referidos  <- breakdowns.pauta_vs_referidos +
                            pauta_vs_referidos_por_antiguedad (agregado
                            Origen×Cohorte). NUNCA se usa
                            `pauta_vs_referidos_por_antiguedad_detalle`: esa
                            función expone la columna "Cliente" (nombre real)
                            fila por fila — PII directo, queda fuera del
                            payload a propósito (sigue intacta en la UI
                            interactiva, ver `pauta_vs_referidos_antiguedad.py`).
  3. canales_y_campanas  <- cierres_por_canal + closures_by_campaign +
                            closures_by_publication + closures_by_origen_pauta
  4. evolucion_temporal  <- closures_by_channel_over_time
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.analytics.breakdowns import (
    cierres_por_canal,
    pauta_vs_referidos,
    pauta_vs_referidos_por_antiguedad,
)
from src.analytics.closures_by_campaign import closures_by_campaign
from src.analytics.closures_by_channel_over_time import closures_by_channel_over_time
from src.analytics.closures_by_publication import closures_by_origen_pauta, closures_by_publication
from src.analytics.filters import filter_by_month
from src.analytics.funnel import funnel_by_advisor
from src.analytics.report_payload_common import category_breakdown_payload, monthly_series_stats

GRUPOS_ORDEN = ["embudo_por_asesor", "pauta_vs_referidos", "canales_y_campanas", "evolucion_temporal"]

GRUPOS_TITULOS = {
    "embudo_por_asesor": "Embudo por asesor (asignados, calificados, cierres)",
    "pauta_vs_referidos": "Pauta vs. Referidos y antigüedad del lead",
    "canales_y_campanas": "Cierres por canal, campaña, publicación y origen de pauta",
    "evolucion_temporal": "Evolución mensual de cierres por canal (pauta directa vs. referido)",
}


def _build_embudo_por_asesor(df: pd.DataFrame, year: int, month: int) -> dict:
    df_period = filter_by_month(df, date(year, month, 1))
    tabla = funnel_by_advisor(df_period, df, year, month)
    if tabla.empty:
        return {
            "asesores": [], "total_asignados": 0, "total_calificados": 0,
            "total_cierres_pauta": 0, "total_cierres_totales": 0,
        }
    return {
        "asesores": tabla.to_dict(orient="records"),
        "total_asignados": int(tabla["Asignados"].sum()),
        "total_calificados": int(tabla["Calificados"].sum()),
        "total_cierres_pauta": int(tabla["Cierres Pauta"].sum()),
        "total_cierres_totales": int(tabla["Cierres Totales"].sum()),
    }


def _build_pauta_vs_referidos(df: pd.DataFrame, year: int, month: int) -> dict:
    df_period = filter_by_month(df, date(year, month, 1))
    resumen = pauta_vs_referidos(df_period, df, year, month)
    antiguedad = pauta_vs_referidos_por_antiguedad(df_period, df, year, month)
    return {
        "pauta_vs_referidos": resumen.to_dict(orient="records") if not resumen.empty else [],
        "por_antiguedad_cohorte": antiguedad.to_dict(orient="records") if not antiguedad.empty else [],
    }


def _build_canales_y_campanas(df: pd.DataFrame, year: int, month: int, team: str) -> dict:
    df_period = filter_by_month(df, date(year, month, 1))
    return {
        "canal": category_breakdown_payload(cierres_por_canal(df_period, df, year, month, team), "Canal", "Cantidad"),
        "campana": category_breakdown_payload(closures_by_campaign(df, year, month, team), "Campaña", "Total"),
        "publicacion": category_breakdown_payload(closures_by_publication(df, year, month), "Publicacion", "Cierres"),
        "origen_pauta": category_breakdown_payload(closures_by_origen_pauta(df, year, month), "Origen", "Cierres"),
    }


def _build_evolucion_temporal(df: pd.DataFrame) -> dict:
    datos = closures_by_channel_over_time(df)
    if datos.empty:
        return {"series_por_canal": {}}
    agregado = datos.groupby(["Año-Mes", "Canal"], as_index=False)["Total cierres"].sum()
    series = {
        canal: monthly_series_stats(
            agregado[agregado["Canal"] == canal].sort_values("Año-Mes"), "Año-Mes", "Total cierres"
        )
        for canal in sorted(agregado["Canal"].unique())
    }
    return {"series_por_canal": series}


_DIRECT_BUILDERS = {
    "embudo_por_asesor": lambda df, year, month, team: _build_embudo_por_asesor(df, year, month),
    "pauta_vs_referidos": lambda df, year, month, team: _build_pauta_vs_referidos(df, year, month),
    "canales_y_campanas": _build_canales_y_campanas,
    "evolucion_temporal": lambda df, year, month, team: _build_evolucion_temporal(df),
}


def group_payload_builder(group_id: str):
    builder = _DIRECT_BUILDERS[group_id]
    return lambda ctx: builder(ctx.df_clientify, ctx.year, ctx.month, ctx.team)


def build_report_payload(df: pd.DataFrame, year: int, month: int, team: str = "Todos") -> dict:
    """Payload completo de Embudo y Canales — uso directo (tests, scripts),
    sin pasar por `ReportContext`."""
    df = df if df is not None else pd.DataFrame()
    grupos = {gid: _DIRECT_BUILDERS[gid](df, year, month, team) for gid in GRUPOS_ORDEN}
    return {"periodo": f"{month:02d}/{year}", "grupos": grupos}
