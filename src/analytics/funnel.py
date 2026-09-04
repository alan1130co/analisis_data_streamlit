"""Embudo Asignados → Calificados → Cierres por asesor.

Regla de negocio 2026-07-15: la tabla debe listar de forma DINÁMICA a todo
`propietario` con al menos 1 lead asignado (creado) en el período — sin
listas blancas/negras de asesores. `is_asesor_comercial`/`NON_COMMERCIAL_OWNERS`
(en metrics.py) siguen existiendo para la tarjeta KPI global "Asignados", pero
NUNCA se aplican acá: este módulo no los importa a propósito.

Regla de negocio 2026-09-03: la columna "Asignados" de ESTA tabla (no la
tarjeta KPI global) se restringe a los asesores "de planta" (`PLANTA_ADVISORS`)
más César Augusto — para cualquier otro `propietario` se fuerza a 0. No hay
ningún campo en los datos que distinga "lead asignado formalmente" de "lead
creado por el asesor a partir de un cierre de referido" (confirmado
explorando el esquema del Excel), así que esto es una lista fija en código,
no una regla derivable de una columna.
"""
from __future__ import annotations

import unicodedata

import pandas as pd

from src.analytics.ad_spend import _clean_importe
from src.analytics.ad_spend_vs_closures import _STAGE_VALUE_COLS
from src.analytics.metrics import is_qualified_mask, is_marketing, valid_closure_estado_mask, get_mask
from src.config.settings import CESAR_AUGUSTO_PREFIX

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
    "% Eficiencia Real",
    "% Efic. Bruta",
    "Cierres Pauta",
    "Cierres Totales",
    "Valor Pauta",
    "Valor Total del Proceso",
]

# Asesores "de planta" — únicos (junto con César Augusto) para los que la
# columna "Asignados" de esta tabla refleja el conteo real de leads creados
# en el período. Para cualquier otro propietario, "Asignados" se fuerza a 0
# (ver docstring del módulo). Comparación sin tildes/mayúsculas vía
# `_normalize_name` para no romper por cómo haya venido tipeado el nombre.
PLANTA_ADVISORS = [
    "Ana Perdomo",
    "Sebastian Ortega",
    "María Del Pilar García Cuenca",
    "Sofía De La Hoz",
    "Marisol Grand López",
]


def _strip_accents(value: str) -> str:
    """Quita tildes/diacríticos, igual que el helper homónimo de metrics.py
    (duplicado a propósito: convención ya usada en este repo, ver ad_spend.py)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def _normalize_name(value) -> str:
    """Normaliza un nombre de asesor para comparar sin depender de
    mayúsculas/tildes: mismo criterio que `propietario` (lower+strip, ya
    aplicado por el loader) más `_strip_accents` (que el loader NO aplica)."""
    return _strip_accents(str(value).strip().lower())


_PLANTA_ADVISORS_NORMALIZED = frozenset(_normalize_name(name) for name in PLANTA_ADVISORS)


def _is_planta_advisor(normalized_name: str) -> bool:
    return normalized_name in _PLANTA_ADVISORS_NORMALIZED


def _is_cesar_advisor(normalized_name: str) -> bool:
    return normalized_name.startswith(CESAR_AUGUSTO_PREFIX)


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


def _sum_value_in_month(
    df: pd.DataFrame, year: int, month: int, predicate=None
) -> float:
    """Suma el valor de cierres válidos (estado != inactivo) del mes,
    opcionalmente filtrados por `predicate(row) -> bool` — mismo criterio de
    validez/período que `_count_closures_in_month`, pero sumando valor en
    vez de contar eventos.

    Usa `_STAGE_VALUE_COLS` (cada fecha de cierre con su PROPIO campo de
    valor: "Fecha de cierre" -> "Valor total del proceso", "Fecha de
    segundo cierre" -> "Valor total segundo cierre", etc. — confirmado
    contra un export real, ver `ad_spend_vs_closures.py`) en vez de
    reutilizar "Valor total del proceso" para las 4 etapas, que es el bug
    conocido y documentado de `revenue_from_redes_monthly` en ese mismo
    módulo — NO se reproduce acá a propósito.
    """
    if df.empty:
        return 0.0
    active = valid_closure_estado_mask(df)
    if predicate is None:
        pred_mask = pd.Series(True, index=df.index)
    elif predicate is is_marketing:
        pred_mask = get_mask(df, "_is_marketing", is_marketing)
    else:
        pred_mask = df.apply(predicate, axis=1)
    total = 0.0
    for date_col, value_col in _STAGE_VALUE_COLS.items():
        if date_col not in df.columns or value_col not in df.columns:
            continue
        dt = pd.to_datetime(df[date_col], errors="coerce")
        mask = (dt.dt.year == year) & (dt.dt.month == month) & active & pred_mask
        if mask.any():
            total += df.loc[mask, value_col].apply(_clean_importe).sum()
    return round(total, 2)


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

    Columnas (orden fijo, ver `_COLUMNS`):
      - Asesor
      - Asignados: leads creados en el mes para ese asesor — SOLO para
        asesores de planta (`PLANTA_ADVISORS`) y César Augusto; para
        cualquier otro propietario (incl. "Sin asesor") vale 0 (regla
        2026-09-03, ver docstring del módulo).
      - Calificados: leads calificados en el mes para ese asesor.
      - % Eficiencia Real: [Cierres Pauta * 100] / Calificados.
      - % Efic. Bruta: [Cierres Pauta * 100] / Asignados.
      - Cierres Pauta: cierres válidos del mes (suma de las 4 fechas) que
        clasifican como Pauta (`is_marketing`, misma regla usada en toda la app).
      - Cierres Totales: todos los cierres válidos del mes (Pauta + Referidos +
        Adicionales), suma de las 4 fechas de cierre.
      - Valor Pauta: suma del valor de los cierres de Pauta del mes (mismo
        universo que "Cierres Pauta"), vía `_sum_value_in_month`.
      - Valor Total del Proceso: suma del valor de TODOS los cierres válidos
        del mes (mismo universo que "Cierres Totales"), sin filtro de canal.

    Orden de filas (regla 2026-09-04, invierte el orden de los grupos 1 y 2
    de la versión anterior — el criterio interno de cada grupo no cambió):
      1. Asesores de planta (`PLANTA_ADVISORS`) primero, ordenados por
         "% Efic. Bruta" descendente — para ellos tiene sentido: su
         "Asignados" es el conteo real.
      2. "Todos los demás" (no-planta, no-César), ordenados por "Cierres
         Totales" descendente — NO por "% Efic. Bruta", porque ese campo
         siempre da 0.0 para este grupo (su "Asignados" es 0 por
         construcción, ver arriba) y no los distinguiría entre sí.
      3. César Augusto, siempre en la última fila de toda la tabla.
    Implementado con 2 columnas auxiliares (`_sort_group`, `_sort_key`) que
    se descartan antes de devolver el resultado.
    """
    empty = pd.DataFrame(columns=_COLUMNS)
    if df_period.empty or "propietario" not in df_period.columns:
        return empty

    rows = []

    df_assigned = df_period[df_period["propietario"].notna()]
    for advisor in df_assigned["propietario"].unique():
        df_adv_period = df_period[df_period["propietario"] == advisor]
        normalized = _normalize_name(advisor)
        is_planta = _is_planta_advisor(normalized)
        is_cesar = _is_cesar_advisor(normalized)
        # Asignados = conteo real solo para planta/César; para el resto, 0
        # (regla 2026-09-03 — no hay campo en los datos que distinga
        # asignación formal de creación por referido, ver docstring del módulo).
        asignados = len(df_adv_period) if (is_planta or is_cesar) else 0
        calificados = int(is_qualified_mask(df_adv_period).sum())

        if "propietario" in df_full.columns:
            df_adv_full = df_full[df_full["propietario"] == advisor]
        else:
            df_adv_full = pd.DataFrame()

        cierres_pauta = _count_closures_in_month(df_adv_full, year, month, is_marketing)
        cierres_totales = _count_closures_in_month(df_adv_full, year, month)
        valor_pauta = _sum_value_in_month(df_adv_full, year, month, is_marketing)
        valor_total = _sum_value_in_month(df_adv_full, year, month)
        efic_global = _pct(cierres_pauta, asignados)
        # Grupo 0 = planta, grupo 1 = "todos los demás", grupo 2 = César
        # (regla 2026-09-04 — planta pasó a ir primero, ya no último).
        sort_group = 0 if is_planta else (2 if is_cesar else 1)

        rows.append({
            "Asesor": str(advisor).title(),
            "Asignados": asignados,
            "Calificados": calificados,
            "% Eficiencia Real": _pct(cierres_pauta, calificados),
            "% Efic. Bruta": efic_global,
            "Cierres Pauta": cierres_pauta,
            "Cierres Totales": cierres_totales,
            "Valor Pauta": valor_pauta,
            "Valor Total del Proceso": valor_total,
            "_sort_group": sort_group,
            # Planta/César: Asignados es real, ordena por % Efic. Bruta.
            # "Todos los demás": % Efic. Bruta siempre es 0.0 (Asignados=0
            # por construcción), así que ordena por Cierres Totales.
            "_sort_key": efic_global if (is_planta or is_cesar) else cierres_totales,
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
                valor_pauta_no_owner = _sum_value_in_month(df_no_owner_full, year, month, is_marketing)
                valor_total_no_owner = _sum_value_in_month(df_no_owner_full, year, month)
                rows.append({
                    "Asesor": "Sin asesor",
                    "Asignados": 0,
                    "Calificados": calificados_no_owner,
                    "% Eficiencia Real": _pct(cierres_pauta_no_owner, calificados_no_owner),
                    "% Efic. Bruta": 0.0,
                    "Cierres Pauta": cierres_pauta_no_owner,
                    "Cierres Totales": cierres_totales_no_owner,
                    "Valor Pauta": valor_pauta_no_owner,
                    "Valor Total del Proceso": valor_total_no_owner,
                    # "Sin asesor" no es planta ni César → va en el grupo "todos
                    # los demás" (1), ordenada por Cierres Totales como el resto.
                    "_sort_group": 1,
                    "_sort_key": cierres_totales_no_owner,
                })

    if not rows:
        return empty

    result = pd.DataFrame(rows)
    result = result.sort_values(
        ["_sort_group", "_sort_key"], ascending=[True, False]
    ).reset_index(drop=True)
    return result[_COLUMNS]
