"""Análisis de motivos de no cierre."""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import is_qualified_mask


def _filter_by_asesor(df: pd.DataFrame, asesor: str | None) -> pd.DataFrame:
    if asesor is None or "propietario" not in df.columns:
        return df
    norm = df["propietario"].astype(str).str.lower().str.strip()
    return df[norm == asesor.lower().strip()]


def qualified_vs_unqualified(
    df_period: pd.DataFrame, asesor: str | None = None
) -> dict[str, int]:
    """Conteo de leads calificados vs no calificados."""
    df = _filter_by_asesor(df_period.copy(), asesor)
    if df.empty:
        return {"Calificados": 0, "No calificados": 0}
    calificados = int(is_qualified_mask(df).sum())
    return {"Calificados": calificados, "No calificados": len(df) - calificados}


def motive_distribution_filtered(
    df: pd.DataFrame,
    year: int,
    month: int,
    advisor: str | None = None,
) -> pd.DataFrame:
    """
    Distribución de motivos para leads creados en el mes/año indicado.
    advisor=None o "Todos" → todos los asesores.
    Vacío/NaN → "Sin diligenciar".
    Columnas: Motivo, Cantidad, Porcentaje. Orden: Cantidad desc.
    """
    if df.empty:
        return pd.DataFrame(columns=["Motivo", "Cantidad", "Porcentaje"])

    creado = pd.to_datetime(df["creado"], errors="coerce")
    mask = (creado.dt.year == year) & (creado.dt.month == month)
    sub = df[mask].copy()

    if advisor and advisor != "Todos" and "propietario" in sub.columns:
        sub = sub[sub["propietario"].astype(str).str.strip() == advisor]

    if sub.empty:
        return pd.DataFrame(columns=["Motivo", "Cantidad", "Porcentaje"])

    if "Motivo de no cierre" in sub.columns:
        raw = sub["Motivo de no cierre"].fillna("").astype(str).str.strip()
    else:
        raw = pd.Series([""] * len(sub), index=sub.index)

    raw = raw.replace({"": "Sin diligenciar", "nan": "Sin diligenciar", "None": "Sin diligenciar"})

    counts = raw.value_counts().reset_index()
    counts.columns = ["Motivo", "Cantidad"]
    total = counts["Cantidad"].sum()
    counts["Porcentaje"] = (counts["Cantidad"] / total * 100).round(1)
    return counts.reset_index(drop=True)


def available_advisors_in_period(
    df: pd.DataFrame, year: int, month: int
) -> list[str]:
    """Lista de asesores con al menos 1 lead creado en ese mes/año."""
    if df.empty or "propietario" not in df.columns:
        return []
    creado = pd.to_datetime(df["creado"], errors="coerce")
    mask = (creado.dt.year == year) & (creado.dt.month == month)
    raw = df[mask]["propietario"].dropna().astype(str).str.strip()
    return sorted([a for a in raw.unique() if a and a.lower() not in {"nan", "none"}])
