"""Comparación de Cierres (1ros) vs Segundos Cierres, agrupados por Año-Mes.

Funciones puras: reciben DataFrame, devuelven DataFrame.
NO importan Streamlit ni nada de la UI.
"""
from __future__ import annotations

import pandas as pd

PRIMER_CIERRE_COL = "Fecha de cierre"
SEGUNDO_CIERRE_COL = "Fecha de segundo cierre"

_COLUMNS = ["Año-Mes", "Cierres", "Segundos cierres"]


def closures_vs_second_closures(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta cierres y segundos cierres por período Año-Mes (YYYY-MM).

    Conteo crudo de registros con fecha no nula en cada columna, agrupados
    por mes — compara el volumen de 1ros vs 2dos cierres a lo largo del
    tiempo. No aplica la regla de "cierre válido" (estado != inactivo) usada
    en las tarjetas KPI: es un conteo simple de fechas presentes, tal como
    lo pidió el negocio para esta gráfica.

    Columnas devueltas: "Año-Mes", "Cierres", "Segundos cierres" (int).
    """
    empty = pd.DataFrame(columns=_COLUMNS)
    if df.empty:
        return empty

    def _period_counts(col: str) -> pd.Series:
        if col not in df.columns:
            return pd.Series(dtype=int)
        fechas = pd.to_datetime(df[col], format="%d/%m/%Y", errors="coerce")
        periodos = fechas.dropna().dt.to_period("M").astype(str)
        return periodos.value_counts()

    cierres = _period_counts(PRIMER_CIERRE_COL)
    segundos = _period_counts(SEGUNDO_CIERRE_COL)

    if cierres.empty and segundos.empty:
        return empty

    out = pd.DataFrame({"Cierres": cierres, "Segundos cierres": segundos})
    out = out.fillna(0).astype(int)
    out = out.sort_index()
    out.index.name = "Año-Mes"
    return out.reset_index()
