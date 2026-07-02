"""Leads y cierres de redes sociales, año a la fecha."""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.analytics.filters import filter_by_month
from src.analytics.metrics import is_marketing, _is_active_estado

_CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]


def social_yearly(
    df: pd.DataFrame,
    year: int,
    advisors: list[str] | None = None,
) -> pd.DataFrame:
    """
    Por cada mes del año: Leads_redes (creados) y Cierres_redes (cualquier cierre del mes).

    Cierres_redes cuenta todas las 4 fechas de cierre de leads de marketing que
    cayeron en ese mes (puede ser un lead creado en cualquier mes).
    """
    if df.empty:
        return pd.DataFrame(
            [{"mes": date(year, m, 1).strftime("%Y-%m"), "Leads_redes": 0, "Cierres_redes": 0}
             for m in range(1, 13)]
        )

    mkt_mask_full = df.apply(is_marketing, axis=1)
    df_mkt_full = df[mkt_mask_full]
    active_mkt_full = df_mkt_full.apply(_is_active_estado, axis=1)

    if advisors and "propietario" in df_mkt_full.columns:
        df_mkt_full = df_mkt_full[df_mkt_full["propietario"].isin(advisors)]

    rows = []
    for month in range(1, 13):
        month_date = date(year, month, 1)

        df_month = filter_by_month(df, month_date)
        if advisors and not df_month.empty and "propietario" in df_month.columns:
            df_month = df_month[df_month["propietario"].isin(advisors)]

        mkt_mask_month = df_month.apply(is_marketing, axis=1) if not df_month.empty else pd.Series([], dtype=bool)
        leads_redes = int(mkt_mask_month.sum())

        cierres_redes = 0
        for col in _CLOSE_COLS:
            if col in df_mkt_full.columns:
                s = pd.to_datetime(df_mkt_full[col], errors="coerce")
                cierres_redes += int(((s.dt.year == year) & (s.dt.month == month) & active_mkt_full).sum())

        rows.append({
            "mes": month_date.strftime("%Y-%m"),
            "Leads_redes": leads_redes,
            "Cierres_redes": cierres_redes,
        })

    return pd.DataFrame(rows)
