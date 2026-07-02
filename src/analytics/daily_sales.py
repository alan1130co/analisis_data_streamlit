"""Ventas (cierres) diarias del mes."""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import _is_active_estado

_CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]


def daily_sales_total(
    df: pd.DataFrame,
    year: int,
    month: int,
    advisors: list[str] | None = None,
) -> pd.DataFrame:
    """
    Cierres por día sumando las 4 fechas de cierre que cayeron en el mes.

    Columnas: dia (date), Cierres.
    """
    df = df.copy()
    if advisors and "propietario" in df.columns:
        df = df[df["propietario"].isin(advisors)]

    active = df.apply(_is_active_estado, axis=1) if not df.empty else pd.Series(dtype=bool)
    records: list = []
    for col in _CLOSE_COLS:
        if col not in df.columns:
            continue
        s = pd.to_datetime(df[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active
        records.extend(s[mask].dt.date.tolist())

    if not records:
        return pd.DataFrame(columns=["dia", "Cierres"])

    counts = pd.Series(records).value_counts().reset_index()
    counts.columns = ["dia", "Cierres"]
    return counts.sort_values("dia").reset_index(drop=True)


def daily_sales_by_advisor(
    df: pd.DataFrame,
    year: int,
    month: int,
    advisors: list[str] | None = None,
) -> pd.DataFrame:
    """
    Cierres por día y asesor.

    Columnas: dia (date), propietario, Cierres.
    """
    df = df.copy()
    if advisors and "propietario" in df.columns:
        df = df[df["propietario"].isin(advisors)]

    active = df.apply(_is_active_estado, axis=1) if not df.empty else pd.Series(dtype=bool)
    parts: list[pd.DataFrame] = []
    for col in _CLOSE_COLS:
        if col not in df.columns:
            continue
        s = pd.to_datetime(df[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active
        if not mask.any():
            continue
        subset = df.loc[mask, ["propietario"]].copy()
        subset["dia"] = s[mask].dt.date.values
        parts.append(subset)

    if not parts:
        return pd.DataFrame(columns=["dia", "propietario", "Cierres"])

    combined = pd.concat(parts, ignore_index=True)
    combined = combined[combined["propietario"].notna()]
    if combined.empty:
        return pd.DataFrame(columns=["dia", "propietario", "Cierres"])

    result = combined.groupby(["dia", "propietario"]).size().reset_index(name="Cierres")
    return result.sort_values("dia").reset_index(drop=True)
