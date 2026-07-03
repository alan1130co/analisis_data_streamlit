"""Tendencia mensual de Asignados, Calificados y Cierres."""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.analytics.filters import filter_by_month
from src.analytics.metrics import is_qualified_mask, _is_valid_closure_estado
from src.config.settings import FOUNDING_DATE


_CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]


def _count_cierres_en_mes(df: pd.DataFrame, active: pd.Series, year: int, month: int) -> int:
    """Cuenta cierres válidos (Activo) del mes iterando las 4 columnas de fecha de cierre."""
    if df.empty:
        return 0
    total = 0
    for col in _CLOSE_COLS:
        if col not in df.columns:
            continue
        s = pd.to_datetime(df[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active
        total += int(mask.sum())
    return total


def monthly_trend(
    df: pd.DataFrame,
    end_year: int,
    end_month: int,
    advisors: list[str] | None = None,
) -> pd.DataFrame:
    """
    Tendencia mensual desde FOUNDING_DATE hasta (end_year, end_month) inclusive.

    Columnas: mes (YYYY-MM), Asignados, Calificados, Cierres.
    Meses sin datos aparecen con ceros para no dejar huecos en el gráfico.
    """
    df_full = df[df["propietario"].isin(advisors)] if advisors and "propietario" in df.columns else df
    active_full = df_full.apply(_is_valid_closure_estado, axis=1) if not df_full.empty else pd.Series(dtype=bool)

    months: list[date] = []
    y, m = FOUNDING_DATE
    while (y < end_year) or (y == end_year and m <= end_month):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m, y = 1, y + 1

    rows = []
    for month_date in months:
        df_month = filter_by_month(df_full, month_date)

        asignados = int(df_month["propietario"].notna().sum()) if not df_month.empty and "propietario" in df_month.columns else 0
        calificados = int(is_qualified_mask(df_month).sum()) if not df_month.empty else 0
        cierres = _count_cierres_en_mes(df_full, active_full, month_date.year, month_date.month)

        rows.append({
            "mes": month_date.strftime("%Y-%m"),
            "Asignados": asignados,
            "Calificados": calificados,
            "Cierres": cierres,
        })

    return pd.DataFrame(rows)
