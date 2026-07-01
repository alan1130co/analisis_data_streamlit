"""Embudo Asignados → Calificados → Cierres por asesor."""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import is_qualified_mask

_CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]


def _infer_period(df_period: pd.DataFrame) -> tuple[int, int]:
    dates = pd.to_datetime(df_period["creado"], errors="coerce").dropna()
    if dates.empty:
        now = pd.Timestamp.now()
        return int(now.year), int(now.month)
    first = dates.iloc[0]
    return int(first.year), int(first.month)


def _closures_in_month_mask(df: pd.DataFrame, year: int, month: int) -> pd.Series:
    # Solo "Fecha de cierre" (1ra columna), consistente con total_cierres
    if "Fecha de cierre" in df.columns:
        dt = pd.to_datetime(df["Fecha de cierre"], errors="coerce")
        return (dt.dt.year == year) & (dt.dt.month == month)
    return pd.Series(False, index=df.index)


def funnel_by_advisor(
    df_period: pd.DataFrame, df_full: pd.DataFrame
) -> pd.DataFrame:
    """
    Desglose del embudo por asesor, incluyendo 'Sin asesor' para cierres sin propietario.

    Columnas: Asesor, Asignados, Calificados, Cierres, % Efic.
    Cierres = todos los cierres del mes (suma de las 4 fechas de cierre).
    Solo incluye filas con al menos 1 cierre en el período.
    """
    empty = pd.DataFrame(
        columns=["Asesor", "Asignados", "Calificados", "Cierres", "% Efic."]
    )
    if df_period.empty or "propietario" not in df_period.columns:
        return empty

    year, month = _infer_period(df_period)
    rows = []

    # Asesores con propietario asignado
    df_assigned = df_period[df_period["propietario"].notna()]
    for advisor in df_assigned["propietario"].unique():
        df_adv_period = df_period[df_period["propietario"] == advisor]
        asignados = len(df_adv_period)
        calificados = int(is_qualified_mask(df_adv_period).sum())

        if "propietario" in df_full.columns:
            df_adv_full = df_full[df_full["propietario"] == advisor]
        else:
            df_adv_full = pd.DataFrame()

        todos_mask = _closures_in_month_mask(df_adv_full, year, month) if not df_adv_full.empty else pd.Series([], dtype=bool)
        todos = int(todos_mask.sum())

        pct_efic = round(todos / asignados * 100, 1) if asignados else 0.0

        rows.append({
            "Asesor": str(advisor).title(),
            "Asignados": asignados,
            "Calificados": calificados,
            "Cierres": todos,
            "% Efic.": pct_efic,
        })

    # Leads sin propietario que tienen cierres en el mes → "Sin asesor"
    if "propietario" in df_full.columns:
        df_no_owner_full = df_full[df_full["propietario"].isna()]
        if not df_no_owner_full.empty:
            todos_no_owner_mask = _closures_in_month_mask(df_no_owner_full, year, month)
            todos_no_owner = int(todos_no_owner_mask.sum())
            if todos_no_owner >= 1:
                df_no_owner_period = df_period[df_period["propietario"].isna()]
                calificados_no_owner = int(is_qualified_mask(df_no_owner_period).sum()) if not df_no_owner_period.empty else 0
                rows.append({
                    "Asesor": "Sin asesor",
                    "Asignados": 0,
                    "Calificados": calificados_no_owner,
                    "Cierres": todos_no_owner,
                    "% Efic.": 0.0,
                })

    if not rows:
        return empty

    result = pd.DataFrame(rows)
    result = result[result["Cierres"] >= 1]
    if result.empty:
        return empty
    return result.sort_values("Asignados", ascending=False).reset_index(drop=True)
