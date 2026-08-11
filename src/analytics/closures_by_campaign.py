"""Cálculo de cierres por Campaña - pauta.

Funciones puras: reciben DataFrame, devuelven DataFrame.
NO importan Streamlit ni nada de la UI.
"""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import get_mask, is_marketing, valid_closure_estado_mask

CATEGORY_COLUMN = "Campaña - pauta"
CATEGORY_LABEL = "Campaña"

_CLOSURE_COLS = [
    "Fecha de cierre", "Fecha de segundo cierre",
    "Fecha de tercer cierre", "Fecha de 4to cierre",
]


def closures_by_campaign(
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Todos",
) -> pd.DataFrame:
    """Distribución de cierres del mes por "Campaña - pauta", filtrada por equipo.

    Cuenta cierres válidos (estado != "inactivo") sumando las 4 fechas de
    cierre que caen en el mes, igual criterio que el resto de los
    desgloses por categoría (`closures_by_process_type`, etc.).

    Columnas: Campaña, Total, Porcentaje.
    """
    empty = pd.DataFrame(columns=[CATEGORY_LABEL, "Total", "Porcentaje"])
    if df_full.empty or CATEGORY_COLUMN not in df_full.columns:
        return empty

    active = valid_closure_estado_mask(df_full)
    mkt_mask = get_mask(df_full, "_is_marketing", is_marketing)

    campanas = []
    for col in _CLOSURE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active
        if team == "Marketing (pautas)":
            mask = mask & mkt_mask
        elif team == "Referidos":
            mask = mask & ~mkt_mask
        sub = df_full[mask]
        if sub.empty:
            continue
        campana = sub[CATEGORY_COLUMN].fillna("").astype(str).str.strip()
        campana = campana.mask(
            campana.eq("") | campana.str.lower().isin({"nan", "none"}),
            "Sin campaña",
        )
        campanas.append(campana)

    if not campanas:
        return empty

    out = pd.concat(campanas).value_counts().reset_index()
    out.columns = [CATEGORY_LABEL, "Total"]
    total = int(out["Total"].sum())
    out["Porcentaje"] = (out["Total"] / total * 100).round(1)
    return out.sort_values("Total", ascending=False).reset_index(drop=True)


def available_periods(df_full: pd.DataFrame) -> list[tuple[int, int]]:
    """Lista de (año, mes) con al menos un cierre, de más reciente a más antiguo."""
    periods: set[tuple[int, int]] = set()
    for col in _CLOSURE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce").dropna()
        for ts in s:
            periods.add((ts.year, ts.month))
    return sorted(periods, reverse=True)
