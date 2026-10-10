"""Payload de datos agregados para el análisis de IA de la pestaña
"Segmentación Clave" (ver `src/analytics/report_payload.py` para el mismo
patrón aplicado a Marketing, y `src/reports/section_registry.py` para cómo
se conecta esto al orquestador genérico).

Regla de oro (CLAUDE.md): esta capa no sabe nada de Streamlit. La IA no hace
aritmética (todo llega ya agregado vía `category_breakdown_payload`) y el
payload nunca contiene filas individuales de Clientify — las 7 gráficas de
`src/ui/sections/closures_by_*.py` ya devuelven tablas agregadas por
categoría (Label/Total/Porcentaje), nunca una fila por contacto.

Las 7 gráficas se agrupan en 3 grupos lógicos:
  1. geografia_cierres  <- closures_by_country + closures_by_state + closures_by_city
  2. perfil_cliente     <- closures_by_age + closures_by_gender (estimado)
  3. proceso_sector     <- closures_by_process_type + closures_by_sector
"""
from __future__ import annotations

import pandas as pd

from src.analytics.closures_by_age import closures_by_age
from src.analytics.closures_by_city import closures_by_city
from src.analytics.closures_by_country import closures_by_country
from src.analytics.closures_by_gender import closures_by_gender
from src.analytics.closures_by_process_type import closures_by_process_type
from src.analytics.closures_by_sector import closures_by_sector
from src.analytics.closures_by_state import closures_by_state
from src.analytics.report_payload_common import category_breakdown_payload

GRUPOS_ORDEN = ["geografia_cierres", "perfil_cliente", "proceso_sector"]

GRUPOS_TITULOS = {
    "geografia_cierres": "Geografía de los cierres (país, estado/provincia, ciudad)",
    "perfil_cliente": "Perfil del cliente que cierra (edad, género estimado)",
    "proceso_sector": "Tipo de proceso y sector de los cierres",
}


def _build_geografia(df: pd.DataFrame, year: int, month: int, team: str) -> dict:
    return {
        "pais": category_breakdown_payload(closures_by_country(df, year, month, team), "país", "Total"),
        "estado_provincia": category_breakdown_payload(closures_by_state(df, year, month, team), "Estado/Provincia", "Total"),
        "ciudad": category_breakdown_payload(closures_by_city(df, year, month, team), "Ciudad", "Total"),
    }


def _build_perfil_cliente(df: pd.DataFrame, year: int, month: int, team: str) -> dict:
    return {
        "rango_edad": category_breakdown_payload(closures_by_age(df, year, month, team), "Rango de edad", "Total"),
        "genero_estimado": category_breakdown_payload(closures_by_gender(df, year, month, team), "Género", "Cantidad"),
        "nota_genero": (
            "SUPUESTO: el género es una ESTIMACIÓN heurística a partir del "
            "primer nombre (gender-guesser + listas + sufijos, default "
            "'Hombre') — no es un dato declarado por el cliente. Trátalo "
            "como aproximado, nunca como un hecho confirmado."
        ),
    }


def _build_proceso_sector(df: pd.DataFrame, year: int, month: int, team: str) -> dict:
    return {
        "tipo_proceso": category_breakdown_payload(closures_by_process_type(df, year, month, team), "Tipo de proceso", "Total"),
        "sector": category_breakdown_payload(closures_by_sector(df, year, month, team), "Sector", "Total"),
    }


_GRUPO_BUILDERS = {
    "geografia_cierres": _build_geografia,
    "perfil_cliente": _build_perfil_cliente,
    "proceso_sector": _build_proceso_sector,
}


def group_payload_builder(group_id: str):
    """`lambda ctx: ...` — adapta el builder del grupo (que toma `df, year,
    month, team` posicionales) al `ReportContext` genérico (ver
    `src/reports/section_types.py`)."""
    builder = _GRUPO_BUILDERS[group_id]
    return lambda ctx: builder(ctx.df_clientify, ctx.year, ctx.month, ctx.team)


def build_report_payload(df: pd.DataFrame, year: int, month: int, team: str = "Todos") -> dict:
    """Payload completo de Segmentación Clave — uso directo (tests, scripts),
    sin pasar por `ReportContext`."""
    df = df if df is not None else pd.DataFrame()
    grupos = {gid: _GRUPO_BUILDERS[gid](df, year, month, team) for gid in GRUPOS_ORDEN}
    return {"periodo": f"{month:02d}/{year}", "grupos": grupos}
