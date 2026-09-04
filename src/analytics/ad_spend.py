"""Procesamiento del gasto en pauta publicitaria (Meta Ads): limpieza y
agregación mensual del reporte de Facturación/Inversión.

Funciones puras: reciben DataFrame, devuelven DataFrame.
NO importan Streamlit ni saben leer archivos — eso vive en
`src/data_sources/ad_spend_loader.py`.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

FECHA_COL = "Fecha"
DIVISA_COL = "Divisa"
IMPORTE_COL = "Importe"
TRANSACTION_ID_COL = "Identificador de la transacción"

# Ya sin tildes (ver _strip_accents) — cubre "USD", "DÓLARES"/"DOLARES" y
# "US DOLLARS" tal como las pidió el negocio.
_USD_DIVISA_VALUES = {"USD", "DOLARES", "US DOLLARS"}

# Pública (sin guion bajo) — reutilizada por `ad_spend_vs_closures.py` para
# que las etiquetas "Mes_Año" sean idénticas carácter a carácter en ambos
# datasets antes de cruzarlos por esa columna.
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_PREPARED_COLUMNS = [FECHA_COL, DIVISA_COL, IMPORTE_COL, "Año", "Mes_num", "Mes_Año"]
_MONTHLY_COLUMNS = ["Mes_Año", IMPORTE_COL]
_MONTHLY_WITH_PERIOD_COLUMNS = ["Año", "Mes_num", "Mes_Año", IMPORTE_COL]


def _strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def _clean_importe(value) -> float:
    """Limpia un valor de 'Importe': quita símbolos/espacios y normaliza el
    formato europeo de miles/decimales (1.234,56 -> 1234.56) antes de
    convertir a float.

    Regla: si aparecen '.' y ',' juntos se asume formato europeo ('.' =
    separador de miles, ',' = decimal) — es el formato del reporte de
    Facturación de Meta que pidió el negocio. Si solo aparece ',' también se
    trata como decimal europeo. Si solo aparece '.' se deja como está
    (formato numérico estándar).
    """
    if pd.isna(value):
        return 0.0
    s = str(value).strip()
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def combine_ad_spend_sources(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Une varios reportes de Facturación de Meta Ads (histórico + reportes
    nuevos de distintas cuentas) en un único DataFrame.

    Deduplica por `TRANSACTION_ID_COL` para no sumar dos veces un cobro que
    caiga en el rango de fechas de más de un archivo (histórico y reporte
    nuevo suelen solaparse unos días). Si esa columna no viene en los
    archivos, se concatena sin deduplicar.
    """
    non_empty = [f for f in frames if f is not None and not f.empty]
    if not non_empty:
        return pd.DataFrame()

    combined = pd.concat(non_empty, ignore_index=True)
    if TRANSACTION_ID_COL in combined.columns:
        combined = combined.drop_duplicates(subset=[TRANSACTION_ID_COL])
    return combined


def prepare_ad_spend(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia el reporte de Meta Ads: parsea 'Fecha', filtra 'Divisa' a USD,
    limpia 'Importe' y agrega columnas Año/Mes_num/Mes_Año.

    Fila a fila (sin agrupar todavía) — usado por `monthly_ad_spend`.
    """
    empty = pd.DataFrame(columns=_PREPARED_COLUMNS)
    required = {FECHA_COL, DIVISA_COL, IMPORTE_COL}
    if df.empty or not required.issubset(df.columns):
        return empty

    out = df.copy()
    out[FECHA_COL] = pd.to_datetime(out[FECHA_COL], errors="coerce", dayfirst=True)

    divisa_norm = out[DIVISA_COL].fillna("").astype(str).str.strip().str.upper().apply(_strip_accents)
    out = out[divisa_norm.isin(_USD_DIVISA_VALUES)].copy()
    if out.empty:
        return empty

    out[IMPORTE_COL] = out[IMPORTE_COL].apply(_clean_importe)
    out = out.dropna(subset=[FECHA_COL])
    if out.empty:
        return empty

    out["Año"] = out[FECHA_COL].dt.year
    out["Mes_num"] = out[FECHA_COL].dt.month
    out["Mes_Año"] = out["Mes_num"].map(MESES_ES) + " " + out["Año"].astype(str)
    return out


def monthly_ad_spend(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa el gasto en pauta (suma de 'Importe') por Mes_Año, ordenado
    cronológicamente (no alfabéticamente — "Enero" > "Diciembre" en ASCII).

    Columnas devueltas: "Mes_Año", "Importe" (float, suma mensual en USD).
    """
    prepared = prepare_ad_spend(df)
    if prepared.empty:
        return pd.DataFrame(columns=_MONTHLY_COLUMNS)

    grouped = (
        prepared.groupby(["Año", "Mes_num", "Mes_Año"])[IMPORTE_COL]
        .sum()
        .reset_index()
        .sort_values(["Año", "Mes_num"])
    )
    return grouped[_MONTHLY_COLUMNS].reset_index(drop=True)


def monthly_ad_spend_with_period(df: pd.DataFrame) -> pd.DataFrame:
    """Como `monthly_ad_spend` pero conserva 'Año' y 'Mes_num' además de
    'Mes_Año' — usado por `ad_spend_vs_closures.py` para cruces que
    necesitan filtrar/ordenar por período numérico (p.ej. "desde enero
    2025") sin volver a parsear el texto de 'Mes_Año'.

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Importe".
    """
    prepared = prepare_ad_spend(df)
    if prepared.empty:
        return pd.DataFrame(columns=_MONTHLY_WITH_PERIOD_COLUMNS)

    grouped = (
        prepared.groupby(["Año", "Mes_num", "Mes_Año"])[IMPORTE_COL]
        .sum()
        .reset_index()
        .sort_values(["Año", "Mes_num"])
    )
    return grouped[_MONTHLY_WITH_PERIOD_COLUMNS].reset_index(drop=True)


# --- Selectores independientes Año/Mes de las 6 gráficas de "Marketing e
# Inversión" (src/ui/sections/ad_spend*.py). Funciones puras/testeables acá
# para que las 6 compartan EXACTAMENTE la misma lógica de parseo/filtrado —
# ninguna la reimplementa por su cuenta.
TODOS = "Todos"
_MESES_ES_INV = {nombre: num for num, nombre in MESES_ES.items()}


def parse_mes_anio(label: str) -> tuple[int, int]:
    """Convierte una etiqueta "Mes Año" (p.ej. "Marzo 2025", el formato que
    ya arma todo este módulo vía `MESES_ES[mes] + " " + año`) de vuelta a
    `(año, mes_num)`. Es el inverso exacto de esa construcción."""
    mes_nombre, anio_str = label.rsplit(" ", 1)
    return int(anio_str), _MESES_ES_INV[mes_nombre]


def anios_disponibles(labels: list[str]) -> list[int]:
    """Años únicos presentes en una lista de etiquetas "Mes Año", ordenados
    ascendente — usado para armar las opciones del selector "Año" de cada
    gráfica (cada una calcula el suyo a partir de sus propios datos, no un
    rango hardcodeado)."""
    return sorted({parse_mes_anio(label)[0] for label in labels})


def filter_by_anio_mes(labels: list[str], anio: int | str, mes: str) -> list[str]:
    """Filtra `labels` ("Mes Año") por año/mes elegidos en los 2 selectores
    independientes. `anio`: `TODOS` o un año puntual (int). `mes`: `TODOS` o
    un nombre de mes en español (ver `MESES_ES`). Ambos criterios se
    combinan con AND; cualquiera de los dos en `TODOS` no filtra por ese eje.
    Preserva el orden original de `labels`.

    Año=TODOS + Mes=específico devuelve ese mes de TODOS los años presentes
    (p.ej. "Marzo 2025" y "Marzo 2026" juntos) — comparación año contra año,
    intencional, no un caso a excluir.
    """
    result = []
    for label in labels:
        y, m = parse_mes_anio(label)
        if anio != TODOS and y != anio:
            continue
        if mes != TODOS and MESES_ES[m] != mes:
            continue
        result.append(label)
    return result
