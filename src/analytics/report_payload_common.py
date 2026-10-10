"""Helpers compartidos por los payload builders de las secciones NUEVAS del
reporte de IA (Segmentación Clave, Embudo y Canales, Gestión Comercial) —
`src/analytics/report_payload.py` (Marketing) no se tocó para no arriesgar
sus tests existentes, así que estos helpers viven acá como la base común
para las secciones agregadas después.

Mismas reglas que Marketing (ver docstring de `report_payload.py`): la IA
nunca hace aritmética (todo llega ya sumado/promediado) y el payload NUNCA
contiene filas individuales de contacto de Clientify — solo agregados por
categoría o por período, construidos a partir de los DataFrames YA
agregados que devuelven `analytics/closures_by_*.py` y similares.
"""
from __future__ import annotations

import pandas as pd


def round_value(value) -> float:
    return round(float(value), 2)


def category_breakdown_payload(df: pd.DataFrame, label_col: str, value_col: str, top_n: int = 10) -> dict:
    """Agregado de una tabla de categorías (salida típica de
    `analytics/closures_by_*.py`: Label/Total|Cantidad/Porcentaje) — total
    general, cantidad de categorías distintas, la categoría líder y el
    top-N por volumen. Nunca incluye filas individuales de contacto porque
    `df` ya viene agregado por categoría desde el analytics correspondiente."""
    if df is None or df.empty or label_col not in df.columns or value_col not in df.columns:
        return {"total": 0, "cantidad_categorias": 0, "categoria_lider": None, "top_categorias": []}

    ordenado = df.sort_values(value_col, ascending=False)
    pct_col = "Porcentaje" if "Porcentaje" in df.columns else None
    top = []
    for _, row in ordenado.head(top_n).iterrows():
        item = {"categoria": str(row[label_col]), "cantidad": int(row[value_col])}
        if pct_col:
            item["porcentaje"] = float(row[pct_col])
        top.append(item)

    return {
        "total": int(ordenado[value_col].sum()),
        "cantidad_categorias": int(len(ordenado)),
        "categoria_lider": top[0] if top else None,
        "top_categorias": top,
    }


def _numeric_series(df: pd.DataFrame, label_col: str, value_col: str, label_key: str) -> dict:
    serie = [{label_key: row[label_col], "valor": round_value(row[value_col])} for _, row in df.iterrows()]
    valores = [p["valor"] for p in serie]
    if not valores:
        return {"serie": [], "promedio": 0.0, "mejor": None, "peor": None, "tendencia": "sin_datos"}

    promedio = round_value(sum(valores) / len(valores))
    mejor = max(serie, key=lambda p: p["valor"])
    peor = min(serie, key=lambda p: p["valor"])

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

    return {"serie": serie, "promedio": promedio, "mejor": mejor, "peor": peor, "tendencia": tendencia}


def monthly_series_stats(df: pd.DataFrame, month_col: str, value_col: str) -> dict:
    """Serie mensual + estadísticos (promedio, mejor/peor mes, tendencia) —
    mismo criterio que `report_payload._series_stats` (Marketing), pero
    parametrizado por el nombre de la columna de mes, porque las secciones
    nuevas usan etiquetas distintas ('Año-Mes', 'mes') según el analytics
    de origen."""
    if df is None or df.empty or month_col not in df.columns or value_col not in df.columns:
        return {"serie_mensual": [], "promedio": 0.0, "mejor_mes": None, "peor_mes": None, "tendencia": "sin_datos"}
    stats = _numeric_series(df, month_col, value_col, "mes")
    return {
        "serie_mensual": stats["serie"],
        "promedio": stats["promedio"],
        "mejor_mes": stats["mejor"],
        "peor_mes": stats["peor"],
        "tendencia": stats["tendencia"],
    }


def daily_series_stats(df: pd.DataFrame, day_col: str, value_col: str) -> dict:
    """Serie diaria + estadísticos — mismo criterio que `monthly_series_stats`
    pero día a día (ventas diarias del mes en Gestión Comercial)."""
    if df is None or df.empty or day_col not in df.columns or value_col not in df.columns:
        return {"serie_diaria": [], "promedio": 0.0, "mejor_dia": None, "peor_dia": None, "tendencia": "sin_datos"}
    df_fmt = df.copy()
    df_fmt[day_col] = df_fmt[day_col].astype(str)
    stats = _numeric_series(df_fmt, day_col, value_col, "dia")
    return {
        "serie_diaria": stats["serie"],
        "promedio": stats["promedio"],
        "mejor_dia": stats["mejor"],
        "peor_dia": stats["peor"],
        "tendencia": stats["tendencia"],
    }
