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

# Ya sin tildes (ver _strip_accents) — cubre "USD", "DÓLARES"/"DOLARES" y
# "US DOLLARS" tal como las pidió el negocio.
_USD_DIVISA_VALUES = {"USD", "DOLARES", "US DOLLARS"}

_MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_PREPARED_COLUMNS = [FECHA_COL, DIVISA_COL, IMPORTE_COL, "Año", "Mes_num", "Mes_Año"]
_MONTHLY_COLUMNS = ["Mes_Año", IMPORTE_COL]


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
    out["Mes_Año"] = out["Mes_num"].map(_MESES_ES) + " " + out["Año"].astype(str)
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
