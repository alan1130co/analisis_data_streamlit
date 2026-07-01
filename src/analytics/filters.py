"""Filtros de período (mes, rango de fechas)."""
from datetime import date

import pandas as pd


def available_months(df: pd.DataFrame, date_col: str = "creado") -> list[date]:
    """Devuelve la lista de meses disponibles en los datos, del más reciente al más viejo."""
    if date_col not in df.columns or df.empty:
        return []
    series = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if series.empty:
        return []
    months = series.dt.to_period("M").unique()
    months_sorted = sorted(months, reverse=True)
    return [m.to_timestamp().date() for m in months_sorted]


def filter_by_month(df: pd.DataFrame, month: date, date_col: str = "creado") -> pd.DataFrame:
    """Filtra los registros cuyo `date_col` pertenece al mes indicado."""
    if date_col not in df.columns or df.empty:
        return df.copy()
    s = pd.to_datetime(df[date_col], errors="coerce")
    mask = (s.dt.year == month.year) & (s.dt.month == month.month)
    return df[mask].copy()


def previous_month(month: date) -> date:
    """Devuelve el primer día del mes anterior al dado."""
    if month.month == 1:
        return date(month.year - 1, 12, 1)
    return date(month.year, month.month - 1, 1)
