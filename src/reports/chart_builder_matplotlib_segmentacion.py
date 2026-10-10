"""Figuras matplotlib para el reporte PDF de "Segmentación Clave" — mismos
datos que `src/ui/sections/closures_by_*.py`, agrupados igual que
`src/analytics/report_payload_segmentacion.py`.

Reemplazos (ver `chart_builder_matplotlib_common.py`): la dona de Tipo de
proceso/Sector/Género y el treemap de Ciudad se reemplazan por barras
horizontales (mismo dato, formas no soportadas nativamente por matplotlib).
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import pandas as pd
from matplotlib.figure import Figure

from src.analytics.closures_by_age import closures_by_age
from src.analytics.closures_by_city import closures_by_city
from src.analytics.closures_by_country import closures_by_country
from src.analytics.closures_by_gender import closures_by_gender
from src.analytics.closures_by_process_type import closures_by_process_type
from src.analytics.closures_by_sector import closures_by_sector
from src.analytics.closures_by_state import closures_by_state
from src.reports.chart_builder_matplotlib_common import horizontal_bar_figure

CHART_TITLES = {
    "pais": "Cierres por país",
    "estado_provincia": "Cierres por estado/provincia",
    "ciudad": "Cierres por ciudad (top 15)",
    "rango_edad": "Cierres por rango de edad",
    "genero_estimado": "Cierres por género (estimado)",
    "tipo_proceso": "Cierres por tipo de proceso",
    "sector": "Cierres por sector",
}


def build_figures_by_group_mpl(
    df: pd.DataFrame, year: int, month: int, team: str,
) -> dict[str, list[tuple[str, Figure]]]:
    por_grupo = {
        "geografia_cierres": [
            (CHART_TITLES["pais"], horizontal_bar_figure(closures_by_country(df, year, month, team), "país", "Total", color="#00B5FF")),
            (CHART_TITLES["estado_provincia"], horizontal_bar_figure(closures_by_state(df, year, month, team), "Estado/Provincia", "Total", color="#00B5FF")),
            (CHART_TITLES["ciudad"], horizontal_bar_figure(closures_by_city(df, year, month, team), "Ciudad", "Total", color="#00B5FF")),
        ],
        "perfil_cliente": [
            (CHART_TITLES["rango_edad"], horizontal_bar_figure(closures_by_age(df, year, month, team), "Rango de edad", "Total", color="#7C3AED")),
            (CHART_TITLES["genero_estimado"], horizontal_bar_figure(closures_by_gender(df, year, month, team), "Género", "Cantidad", color="#FF2D55")),
        ],
        "proceso_sector": [
            (CHART_TITLES["tipo_proceso"], horizontal_bar_figure(closures_by_process_type(df, year, month, team), "Tipo de proceso", "Total", color="#16A34A")),
            (CHART_TITLES["sector"], horizontal_bar_figure(closures_by_sector(df, year, month, team), "Sector", "Total", color="#F59E0B")),
        ],
    }
    return {
        grupo_id: [(titulo, fig) for titulo, fig in pares if fig is not None]
        for grupo_id, pares in por_grupo.items()
    }
