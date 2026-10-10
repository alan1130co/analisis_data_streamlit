"""Payload de datos agregados para el análisis por IA del reporte PDF de
Marketing e Inversión (ver `src/reports/pdf_report.py` y `src/ui/report_
generator.py`).

Regla de oro (CLAUDE.md): esta capa NO sabe nada de Streamlit. Además, acá
se agrega una segunda regla propia de este módulo: la IA NO hace aritmética
— todo lo que recibe ya viene sumado/promediado/comparado en Python. Y una
tercera: el payload NUNCA debe contener PII ni filas de contacto de
Clientify, solo agregados por mes — por eso todas las funciones de este
archivo reutilizan los `combine_*`/`calculate_*`/`monthly_*` ya existentes
en `ad_spend.py`/`ad_spend_vs_closures.py` (que agrupan por mes) en vez de
tocar `df_clientify` fila por fila.

Las 9 gráficas de "Marketing e Inversión" (`src/ui/sections/ad_spend*.py`)
se agrupan en 5 grupos lógicos — una llamada a la IA por grupo (ver
`src/data_sources/ai_provider.py` y el orquestador del reporte):

  1. gasto_y_facturado          <- ad_spend.py + ad_spend_billed.py
  2. gasto_vs_ingresos_y_roas   <- ad_spend_vs_revenue.py + ad_spend_roas.py
  3. costo_por_lead             <- ad_spend_cost_per_lead.py
  4. roas_total                 <- ad_spend_total_roas.py
  5. cierres_y_valor_proceso    <- ad_spend_vs_closures.py + ad_spend_vs_process_value.py + ad_spend_vs_process_value_roas.py
"""
from __future__ import annotations

import pandas as pd

from src.analytics.ad_spend import (
    TODOS,
    combine_real_vs_billed_monthly,
    monthly_ad_spend,
    monthly_ad_spend_with_period,
    parse_mes_anio,
)
from src.analytics.ad_spend_vs_closures import (
    calculate_pauta_process_value_chart,
    calculate_redes_initial_payments_chart,
    calculate_redes_revenue_chart,
    closures_from_redes_monthly,
    closures_from_redes_total_monthly,
    combine_ad_spend_and_closures,
    combine_ad_spend_and_cost_per_lead,
    combine_ad_spend_and_pauta_process_value,
    combine_ad_spend_process_value_and_roas,
    combine_ad_spend_revenue_and_roas,
    combine_ad_spend_total_revenue_and_roas,
)

PERIODO_TODOS = TODOS  # re-exportado: valor que acepta `anio` para "sin filtro de año"

GRUPOS_ORDEN = [
    "gasto_y_facturado",
    "gasto_vs_ingresos_y_roas",
    "costo_por_lead",
    "roas_total",
    "cierres_y_valor_proceso",
]

GRUPOS_TITULOS = {
    "gasto_y_facturado": "Gasto en pauta y facturación real vs. facturada",
    "gasto_vs_ingresos_y_roas": "Gasto en pauta vs. ingresos por redes y ROAS",
    "costo_por_lead": "Costo promedio por lead de redes",
    "roas_total": "ROAS acumulado (gasto total: pauta + honorarios)",
    "cierres_y_valor_proceso": "Cierres de redes y valor total del proceso",
}


def _filter_by_anio(df: pd.DataFrame, anio: int | str) -> pd.DataFrame:
    """Filtra un DataFrame mensual (con columna 'Año' o, si no la tiene,
    'Mes_Año' parseable vía `parse_mes_anio`) al año elegido. `anio ==
    PERIODO_TODOS` devuelve el DataFrame sin tocar."""
    if df.empty or anio == PERIODO_TODOS:
        return df
    if "Año" in df.columns:
        return df[df["Año"] == anio].reset_index(drop=True)
    anios = df["Mes_Año"].apply(lambda label: parse_mes_anio(label)[0])
    return df[anios == anio].reset_index(drop=True)


def _round(value) -> float:
    return round(float(value), 2)


def _series_stats(df: pd.DataFrame, value_col: str) -> dict:
    """Serie mensual + estadísticos YA calculados en Python a partir de
    'Mes_Año'/`value_col`: promedio, mejor mes, peor mes, variación % mes a
    mes, y tendencia (promedio de la 2da mitad del período vs la 1ra). La
    IA solo lee estos números — no debe recalcular ninguno."""
    if df.empty or value_col not in df.columns:
        return {
            "serie_mensual": [],
            "promedio": 0.0,
            "mejor_mes": None,
            "peor_mes": None,
            "variacion_mensual_pct": [],
            "tendencia": "sin_datos",
        }

    serie = [
        {"mes": row["Mes_Año"], "valor": _round(row[value_col])}
        for _, row in df.iterrows()
    ]
    valores = [p["valor"] for p in serie]
    promedio = _round(sum(valores) / len(valores)) if valores else 0.0
    mejor_mes = max(serie, key=lambda p: p["valor"])
    peor_mes = min(serie, key=lambda p: p["valor"])

    variaciones = []
    for i in range(1, len(valores)):
        prev, curr = valores[i - 1], valores[i]
        pct = None if prev == 0 else _round((curr - prev) / prev * 100)
        variaciones.append({"mes": serie[i]["mes"], "variacion_pct": pct})

    tendencia = "sin_datos"
    if len(valores) >= 2:
        mitad = max(len(valores) // 2, 1)
        promedio_1 = sum(valores[:mitad]) / len(valores[:mitad])
        promedio_2 = sum(valores[mitad:]) / len(valores[mitad:]) if valores[mitad:] else promedio_1
        if promedio_1 == 0 and promedio_2 == 0:
            tendencia = "estable"
        elif promedio_2 > promedio_1 * 1.05:
            tendencia = "creciente"
        elif promedio_2 < promedio_1 * 0.95:
            tendencia = "decreciente"
        else:
            tendencia = "estable"

    return {
        "serie_mensual": serie,
        "promedio": promedio,
        "mejor_mes": mejor_mes,
        "peor_mes": peor_mes,
        "variacion_mensual_pct": variaciones,
        "tendencia": tendencia,
    }


def _build_gasto_y_facturado(gasto_raw: pd.DataFrame, billed_raw: pd.DataFrame | None, anio) -> dict:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    facturado_mensual = (
        monthly_ad_spend_with_period(billed_raw) if billed_raw is not None and not billed_raw.empty else pd.DataFrame()
    )
    combinado = _filter_by_anio(combine_real_vs_billed_monthly(gasto_mensual, facturado_mensual), anio)
    diferencia_total = _round(combinado["Diferencia"].sum()) if not combinado.empty else 0.0
    return {
        "gasto_real": _series_stats(combinado, "Importe_Real"),
        "gasto_facturado": _series_stats(combinado, "Importe_Facturado"),
        "diferencia_real_vs_facturado_total": diferencia_total,
    }


def _build_gasto_vs_ingresos_y_roas(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> dict:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_redes_mensual = _filter_by_anio(calculate_redes_revenue_chart(df_clientify), anio)
    ingreso_cuota_inicial_mensual = calculate_redes_initial_payments_chart(df_clientify)
    roas_pauta = _filter_by_anio(
        combine_ad_spend_revenue_and_roas(gasto_mensual, ingreso_cuota_inicial_mensual), anio
    )
    return {
        "ingreso_por_redes_valor_proceso": _series_stats(ingreso_redes_mensual, "Ingreso_Redes"),
        "gasto_pauta": _series_stats(roas_pauta, "Importe"),
        "ingreso_cuota_inicial": _series_stats(roas_pauta, "Ingreso_CuotaInicial"),
        "roas_pauta": _series_stats(roas_pauta, "ROAS"),
    }


def _build_costo_por_lead(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> dict:
    gasto_mensual = monthly_ad_spend(gasto_raw)
    cierres_mensual = closures_from_redes_total_monthly(df_clientify)
    combinado = _filter_by_anio(combine_ad_spend_and_cost_per_lead(gasto_mensual, cierres_mensual), anio)
    return {
        "gasto_pauta": _series_stats(combinado, "Importe"),
        "cierres_redes_total": _series_stats(combinado, "Cierres_Redes"),
        "costo_por_lead": _series_stats(combinado, "Valor_por_Lead"),
    }


def _build_roas_total(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> dict:
    gasto_mensual = monthly_ad_spend_with_period(gasto_raw)
    ingreso_cuota_inicial_mensual = calculate_redes_initial_payments_chart(df_clientify)
    combinado = _filter_by_anio(
        combine_ad_spend_total_revenue_and_roas(gasto_mensual, ingreso_cuota_inicial_mensual), anio
    )
    return {
        "gasto_total_pauta_mas_honorarios": _series_stats(combinado, "Gasto_Total"),
        "ingreso_cuota_inicial": _series_stats(combinado, "Ingreso_CuotaInicial"),
        "roas_total": _series_stats(combinado, "ROAS"),
    }


def _build_cierres_y_valor_proceso(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> dict:
    gasto_mensual = monthly_ad_spend(gasto_raw)
    cierres_mensual = closures_from_redes_monthly(df_clientify)
    cierres_combinado = _filter_by_anio(combine_ad_spend_and_closures(gasto_mensual, cierres_mensual), anio)

    gasto_mensual_wp = monthly_ad_spend_with_period(gasto_raw)
    valor_mensual = calculate_pauta_process_value_chart(df_clientify)
    valor_combinado = _filter_by_anio(
        combine_ad_spend_and_pauta_process_value(gasto_mensual_wp, valor_mensual), anio
    )
    roas_valor_combinado = _filter_by_anio(
        combine_ad_spend_process_value_and_roas(gasto_mensual_wp, valor_mensual), anio
    )

    return {
        "cierres_redes": _series_stats(cierres_combinado, "Cierres_Redes"),
        "valor_total_proceso_pauta": _series_stats(valor_combinado, "Valor_Proceso_Pauta"),
        "roas_valor_proceso": _series_stats(roas_valor_combinado, "ROAS"),
    }


_GRUPO_BUILDERS = {
    "gasto_y_facturado": lambda gasto_raw, df_clientify, billed_raw, anio: _build_gasto_y_facturado(gasto_raw, billed_raw, anio),
    "gasto_vs_ingresos_y_roas": lambda gasto_raw, df_clientify, billed_raw, anio: _build_gasto_vs_ingresos_y_roas(gasto_raw, df_clientify, anio),
    "costo_por_lead": lambda gasto_raw, df_clientify, billed_raw, anio: _build_costo_por_lead(gasto_raw, df_clientify, anio),
    "roas_total": lambda gasto_raw, df_clientify, billed_raw, anio: _build_roas_total(gasto_raw, df_clientify, anio),
    "cierres_y_valor_proceso": lambda gasto_raw, df_clientify, billed_raw, anio: _build_cierres_y_valor_proceso(gasto_raw, df_clientify, anio),
}


def build_report_payload(
    gasto_raw: pd.DataFrame,
    df_clientify: pd.DataFrame,
    billed_raw: pd.DataFrame | None,
    anio: int | str = PERIODO_TODOS,
) -> dict:
    """Payload completo del reporte: un dict por grupo lógico, cada uno con
    series mensuales y estadísticos ya calculados (nunca filas crudas de
    `df_clientify` ni `gasto_raw`/`billed_raw`) — listo para pasarle a
    `src/data_sources/ai_provider.py` como contexto de la IA.

    `gasto_raw`/`billed_raw` son el reporte de Meta Ads ya cargado/combinado
    (mismo insumo que usan las 9 gráficas de `src/ui/sections/ad_spend*.py`)
    — nunca contactos de Clientify, así que no hace falta "despersonalizar"
    nada ahí. `df_clientify` sí puede traer PII en sus columnas crudas, pero
    acá nunca se tocan directamente: solo se le pasa a funciones de
    `ad_spend_vs_closures.py` que ya agregan por mes antes de devolver.
    """
    if gasto_raw is None:
        gasto_raw = pd.DataFrame()
    if df_clientify is None:
        df_clientify = pd.DataFrame()

    grupos = {
        grupo_id: _GRUPO_BUILDERS[grupo_id](gasto_raw, df_clientify, billed_raw, anio)
        for grupo_id in GRUPOS_ORDEN
    }
    return {"periodo": anio, "grupos": grupos}


def group_payload_builder(group_id: str):
    """`lambda ctx: ...` — adapta uno de los builders de `_GRUPO_BUILDERS`
    (que toma `gasto_raw, df_clientify, billed_raw, anio` posicionales) al
    `ReportContext` genérico del orquestador multi-sección (ver
    `src/reports/section_types.py` y `src/reports/section_registry.py`).
    Agregado para reusar este módulo desde el registro de secciones sin
    duplicar los 5 builders de arriba."""
    builder = _GRUPO_BUILDERS[group_id]
    return lambda ctx: builder(ctx.gasto_raw, ctx.df_clientify, ctx.billed_raw, ctx.anio_filter)
