"""Comparación de indicadores entre el mes actual y el mes anterior."""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.analytics.filters import filter_by_month, previous_month
from src.analytics.metrics import compute_all_metrics


def monthly_comparison(
    df: pd.DataFrame,
    current_month: date,
    advisors: list[str] | None = None,
) -> pd.DataFrame:
    """
    Compara 4 indicadores entre el mes actual y el mes anterior.

    Columnas: Indicador, mes_anterior, mes_actual.
    Retorna DataFrame vacío si no hay datos del mes anterior.
    """
    prev = previous_month(current_month)
    df_curr = filter_by_month(df, current_month)
    df_prev = filter_by_month(df, prev)

    if df_prev.empty:
        return pd.DataFrame()

    if advisors and "propietario" in df.columns:
        df_curr = df_curr[df_curr["propietario"].isin(advisors)]
        df_prev = df_prev[df_prev["propietario"].isin(advisors)]

    m_curr = compute_all_metrics(df_curr, df)
    m_prev = compute_all_metrics(df_prev, df)

    rows = [
        ("Asignados",                 m_prev.asignados,              m_curr.asignados),
        ("Calificados",               m_prev.calificados,            m_curr.calificados),
        ("Cierres pauta",             m_prev.cierres_marketing,      m_curr.cierres_marketing),
        ("Cierres referidos",         m_prev.cierres_referidos,      m_curr.cierres_referidos),
        ("Cierres totales (1+2+3+4)", m_prev.total_cierres_general,  m_curr.total_cierres_general),
    ]
    return pd.DataFrame(rows, columns=["Indicador", "mes_anterior", "mes_actual"])
