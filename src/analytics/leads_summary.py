"""Resumen de leads por mes y año."""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.analytics.filters import filter_by_month
from src.analytics.metrics import is_marketing, is_qualified_mask, valid_closure_estado_mask, get_mask


def leads_summary(
    df: pd.DataFrame,
    year: int,
    month: int | None = None,
    advisors: list[str] | None = None,
) -> pd.DataFrame:
    """
    Resumen por mes: Leads, Calificados, Cierres, Referidos.

    Si month=None devuelve todos los meses del año.
    Columnas: mes (YYYY-MM), Leads, Calificados, Cierres, Referidos.
    """
    months = [month] if month is not None else list(range(1, 13))
    rows = []

    for m in months:
        month_date = date(year, m, 1)
        df_month = filter_by_month(df, month_date)

        if advisors and not df_month.empty and "propietario" in df_month.columns:
            df_month = df_month[df_month["propietario"].isin(advisors)]

        leads = len(df_month)

        calificados = int(is_qualified_mask(df_month).sum())

        cierres = 0
        referidos = 0
        if not df_month.empty and "Fecha de cierre" in df_month.columns:
            active = valid_closure_estado_mask(df_month)
            mask_cierre = pd.to_datetime(df_month["Fecha de cierre"], errors="coerce").notna() & active
            cierres = int(mask_cierre.sum())
            mask_referido = ~get_mask(df_month, "_is_marketing", is_marketing)
            referidos = int((mask_referido & mask_cierre).sum())

        rows.append({
            "mes": month_date.strftime("%Y-%m"),
            "Leads": leads,
            "Calificados": calificados,
            "Cierres": cierres,
            "Referidos": referidos,
        })

    return pd.DataFrame(rows)