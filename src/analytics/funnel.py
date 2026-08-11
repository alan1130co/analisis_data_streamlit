"""Embudo Asignados → Calificados → Cierres por asesor.

Regla de negocio 2026-07-15: la tabla debe listar de forma DINÁMICA a todo
`propietario` con al menos 1 lead asignado (creado) en el período — sin
listas blancas/negras de asesores. `is_asesor_comercial`/`NON_COMMERCIAL_OWNERS`
(en metrics.py) siguen existiendo para la tarjeta KPI global "Asignados", pero
NUNCA se aplican acá: este módulo no los importa a propósito.
"""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import is_qualified_mask, is_marketing, valid_closure_estado_mask, get_mask

_CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]

_COLUMNS = [
    "Asesor",
    "Asignados",
    "Calificados",
    "Cierres Pauta",
    "Cierres Totales",
    "% Eficiencia Real",
    "% Efic. Global",
]


def _count_closures_in_month(
    df: pd.DataFrame, year: int, month: int, predicate=None
) -> int:
    """Cuenta cierres válidos (estado != inactivo) del mes, sumando las 4
    columnas de fecha de cierre, opcionalmente filtrados por `predicate(row) -> bool`."""
    if df.empty:
        return 0
    active = valid_closure_estado_mask(df)
    if predicate is None:
        pred_mask = pd.Series(True, index=df.index)
    elif predicate is is_marketing:
        pred_mask = get_mask(df, "_is_marketing", is_marketing)
    else:
        pred_mask = df.apply(predicate, axis=1)
    total = 0
    for col in _CLOSE_COLS:
        if col not in df.columns:
            continue
        dt = pd.to_datetime(df[col], errors="coerce")
        mask = (dt.dt.year == year) & (dt.dt.month == month) & active & pred_mask
        total += int(mask.sum())
    return total


def _pct(numerator: int, denominator: int) -> float:
    """[numerator * 100] / denominator, con guarda de división por cero → 0.0."""
    return round(numerator * 100 / denominator, 1) if denominator else 0.0


def funnel_by_advisor(
    df_period: pd.DataFrame, df_full: pd.DataFrame, year: int, month: int
) -> pd.DataFrame:
    """
    Desglose del embudo por asesor: Asignados → Calificados → Cierres.

    `year`/`month` son OBLIGATORIOS y deben ser el período activo seleccionado
    en el frontend (el mismo usado para construir `df_period` vía
    `filter_by_month`). Antes esta función "adivinaba" el período leyendo la
    primera fecha de `df_period["creado"]`, con fallback silencioso a
    `pd.Timestamp.now()` si `df_period` venía vacío (p.ej. un mes recién
    empezado sin leads creados todavía) — eso hacía que la tabla del Embudo
    se congelara/mostrara el mes del reloj del servidor en vez del período
    elegido en el dropdown. Ver bug 2026-07-?? "desincronización de fechas".

    Incluye a TODO 'propietario' con al menos 1 lead asignado (creado) en el
    período, sin excepción (asesores independientes/free incluidos), más una
    fila "Sin asesor" si hay cierres del mes sobre leads sin propietario (para
    que la suma de "Cierres Totales" siga cuadrando con `total_cierres_general`).

    Columnas:
      - Asesor
      - Asignados: leads creados en el mes para ese asesor.
      - Calificados: leads calificados en el mes para ese asesor.
      - Cierres Pauta: cierres válidos del mes (suma de las 4 fechas) que
        clasifican como Pauta (`is_marketing`, misma regla usada en toda la app).
      - Cierres Totales: todos los cierres válidos del mes (Pauta + Referidos +
        Adicionales), suma de las 4 fechas de cierre.
      - % Eficiencia Real: [Cierres Pauta * 100] / Calificados.
      - % Efic. Global: [Cierres Pauta * 100] / Asignados.
    """
    empty = pd.DataFrame(columns=_COLUMNS)
    if df_period.empty or "propietario" not in df_period.columns:
        return empty

    rows = []

    df_assigned = df_period[df_period["propietario"].notna()]
    for advisor in df_assigned["propietario"].unique():
        df_adv_period = df_period[df_period["propietario"] == advisor]
        asignados = len(df_adv_period)
        calificados = int(is_qualified_mask(df_adv_period).sum())

        if "propietario" in df_full.columns:
            df_adv_full = df_full[df_full["propietario"] == advisor]
        else:
            df_adv_full = pd.DataFrame()

        cierres_pauta = _count_closures_in_month(df_adv_full, year, month, is_marketing)
        cierres_totales = _count_closures_in_month(df_adv_full, year, month)

        rows.append({
            "Asesor": str(advisor).title(),
            "Asignados": asignados,
            "Calificados": calificados,
            "Cierres Pauta": cierres_pauta,
            "Cierres Totales": cierres_totales,
            "% Eficiencia Real": _pct(cierres_pauta, calificados),
            "% Efic. Global": _pct(cierres_pauta, asignados),
        })

    # Leads sin propietario que tienen cierres en el mes → "Sin asesor".
    # Se conserva esta fila (no es un asesor dinámico, es un caso aparte) para
    # que `Cierres Totales`.sum() siga cuadrando con total_cierres_general.
    if "propietario" in df_full.columns:
        df_no_owner_full = df_full[df_full["propietario"].isna()]
        if not df_no_owner_full.empty:
            cierres_totales_no_owner = _count_closures_in_month(df_no_owner_full, year, month)
            if cierres_totales_no_owner >= 1:
                cierres_pauta_no_owner = _count_closures_in_month(df_no_owner_full, year, month, is_marketing)
                df_no_owner_period = df_period[df_period["propietario"].isna()]
                calificados_no_owner = int(is_qualified_mask(df_no_owner_period).sum()) if not df_no_owner_period.empty else 0
                rows.append({
                    "Asesor": "Sin asesor",
                    "Asignados": 0,
                    "Calificados": calificados_no_owner,
                    "Cierres Pauta": cierres_pauta_no_owner,
                    "Cierres Totales": cierres_totales_no_owner,
                    "% Eficiencia Real": _pct(cierres_pauta_no_owner, calificados_no_owner),
                    "% Efic. Global": 0.0,
                })

    if not rows:
        return empty

    result = pd.DataFrame(rows)
    return result.sort_values("Asignados", ascending=False).reset_index(drop=True)
