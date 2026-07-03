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


def is_current_month(month: date, today: date | None = None) -> bool:
    """True si `month` es el mes calendario en curso (según la fecha real de hoy)."""
    today = today or date.today()
    return month.year == today.year and month.month == today.month


def default_month_index(months: list[date], today: date | None = None) -> int:
    """Índice a usar como default del selectbox de período: el último mes COMPLETO.

    Si el mes más reciente con leads (`months[0]`) es el mes en curso, un
    Excel exportado a los pocos días de arrancar ese mes ya trae un puñado
    de leads y lo convertiría en default pese a estar casi vacío — se
    saltea al mes anterior. El mes en curso sigue disponible en la lista,
    solo no es la selección inicial.
    """
    if not months:
        return 0
    if is_current_month(months[0], today) and len(months) > 1:
        return 1
    return 0


def format_month_label(month: date, today: date | None = None) -> str:
    """Etiqueta del selectbox: 'Junio 2026', o 'Julio 2026 (en curso, 3 días)'
    si `month` es el mes calendario en curso."""
    label = month.strftime("%B %Y").capitalize()
    today = today or date.today()
    if is_current_month(month, today):
        dias = today.day
        label += f" (en curso, {dias} día{'s' if dias != 1 else ''})"
    return label
