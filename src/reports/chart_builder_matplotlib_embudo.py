"""Figuras matplotlib para el reporte PDF de "Embudo y Canales" — mismos
datos que `src/ui/sections/funnel.py`/`pauta_vs_referidos*.py`/
`cierres_por_canal.py`/`closures_by_campaign.py`/`closures_by_publication.py`/
`closures_by_channel_over_time.py`, agrupados igual que
`src/analytics/report_payload_embudo.py`.

NUNCA usa `pauta_vs_referidos_por_antiguedad_detalle` (expone "Cliente" con
nombre real) — solo la versión agregada Origen×Cohorte.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from datetime import date

import pandas as pd
from matplotlib.figure import Figure

from src.analytics.breakdowns import cierres_por_canal, pauta_vs_referidos, pauta_vs_referidos_por_antiguedad
from src.analytics.closures_by_campaign import closures_by_campaign
from src.analytics.closures_by_channel_over_time import closures_by_channel_over_time
from src.analytics.closures_by_publication import closures_by_origen_pauta, closures_by_publication
from src.analytics.filters import filter_by_month
from src.analytics.funnel import funnel_by_advisor
from src.reports.chart_builder_matplotlib_common import (
    grouped_bar_over_categories_figure,
    horizontal_bar_figure,
    multi_line_over_time_figure,
)

CHART_TITLES = {
    "embudo_asesor": "Embudo por asesor (Asignados / Calificados / Cierres Pauta)",
    "pauta_vs_referidos": "Pauta vs. Referidos",
    "antiguedad": "Cierres por antigüedad del lead (cohorte)",
    "canal": "Cierres por canal",
    "campana": "Cierres por campaña (top 15)",
    "publicacion": "Cierres por publicación",
    "origen_pauta": "Cierres por origen de pauta (red social)",
    "evolucion_canal": "Evolución mensual de cierres por canal",
}

_COLOR_ASIGNADOS = "#00B5FF"
_COLOR_CALIFICADOS = "#7C3AED"
_COLOR_CIERRES = "#16A34A"
_COLOR_REFERIDOS = "#F59E0B"


def _build_embudo_asesor_fig(df: pd.DataFrame, year: int, month: int) -> Figure | None:
    df_period = filter_by_month(df, date(year, month, 1))
    tabla = funnel_by_advisor(df_period, df, year, month)
    if tabla.empty:
        return None
    tabla = tabla.sort_values("Cierres Totales", ascending=False).head(12)
    return grouped_bar_over_categories_figure(
        tabla, "Asesor",
        [
            ("Asignados", "Asignados", _COLOR_ASIGNADOS),
            ("Calificados", "Calificados", _COLOR_CALIFICADOS),
            ("Cierres Pauta", "Cierres Pauta", _COLOR_CIERRES),
        ],
        title_y="Cantidad",
    )


def _build_antiguedad_fig(df: pd.DataFrame, year: int, month: int) -> Figure | None:
    df_period = filter_by_month(df, date(year, month, 1))
    datos = pauta_vs_referidos_por_antiguedad(df_period, df, year, month)
    if datos.empty:
        return None
    ancho = datos.pivot(index="Cohorte", columns="Origen", values="Cantidad").fillna(0).reset_index()
    specs = [
        (col, col, color) for col, color in (("Pauta", _COLOR_CIERRES), ("Referidos", _COLOR_REFERIDOS))
        if col in ancho.columns
    ]
    return grouped_bar_over_categories_figure(ancho, "Cohorte", specs, title_y="Cantidad de cierres")


def _build_evolucion_canal_fig(df: pd.DataFrame) -> Figure | None:
    datos = closures_by_channel_over_time(df)
    if datos.empty:
        return None
    agregado = datos.groupby(["Año-Mes", "Canal"], as_index=False)["Total cierres"].sum()
    ancho = agregado.pivot(index="Año-Mes", columns="Canal", values="Total cierres").fillna(0).reset_index()
    ancho = ancho.sort_values("Año-Mes")
    specs = [
        (col, col, color) for col, color in (("Pauta directa", _COLOR_CIERRES), ("Referido", _COLOR_REFERIDOS))
        if col in ancho.columns
    ]
    return multi_line_over_time_figure(ancho, "Año-Mes", specs, title_y="Cierres")


def build_figures_by_group_mpl(
    df: pd.DataFrame, year: int, month: int, team: str,
) -> dict[str, list[tuple[str, Figure]]]:
    df_period = filter_by_month(df, date(year, month, 1))
    por_grupo = {
        "embudo_por_asesor": [
            (CHART_TITLES["embudo_asesor"], _build_embudo_asesor_fig(df, year, month)),
        ],
        "pauta_vs_referidos": [
            (CHART_TITLES["pauta_vs_referidos"], horizontal_bar_figure(pauta_vs_referidos(df_period, df, year, month), "Origen", "Cantidad", color=_COLOR_CIERRES)),
            (CHART_TITLES["antiguedad"], _build_antiguedad_fig(df, year, month)),
        ],
        "canales_y_campanas": [
            (CHART_TITLES["canal"], horizontal_bar_figure(cierres_por_canal(df_period, df, year, month, team), "Canal", "Cantidad", color=_COLOR_ASIGNADOS)),
            (CHART_TITLES["campana"], horizontal_bar_figure(closures_by_campaign(df, year, month, team), "Campaña", "Total", color=_COLOR_CALIFICADOS)),
            (CHART_TITLES["publicacion"], horizontal_bar_figure(closures_by_publication(df, year, month), "Publicacion", "Cierres", color=_COLOR_REFERIDOS)),
            (CHART_TITLES["origen_pauta"], horizontal_bar_figure(closures_by_origen_pauta(df, year, month), "Origen", "Cierres", color="#FF2D55")),
        ],
        "evolucion_temporal": [
            (CHART_TITLES["evolucion_canal"], _build_evolucion_canal_fig(df)),
        ],
    }
    return {
        grupo_id: [(titulo, fig) for titulo, fig in pares if fig is not None]
        for grupo_id, pares in por_grupo.items()
    }
