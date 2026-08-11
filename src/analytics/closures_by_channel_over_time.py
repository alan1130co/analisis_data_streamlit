"""Cierres por canal (Pauta directa vs Referidos), discriminados por Primer
Cierre y Segundo Cierre, a lo largo del tiempo (Año-Mes).

Funciones puras: reciben DataFrame, devuelven DataFrame.
NO importan Streamlit ni nada de la UI.
"""
from __future__ import annotations

import pandas as pd

CANAL_OFFLINE_COL = "Canal offline"
PRIMER_CIERRE_COL = "Fecha de cierre"
SEGUNDO_CIERRE_COL = "Fecha de segundo cierre"

# Orígenes que cuentan como "Pauta directa" (Canal offline). Cualquier otro
# valor (incluido vacío/None) cae en "Referido". Comparación normalizada
# (lower + strip) porque `ExcelContactsLoader._normalize()` ya deja "Canal
# offline" en minúsculas — esta lista se define en Title Case por legibilidad
# pero se compara sin distinguir mayúsculas/minúsculas.
PAUTA_DIRECTA_ORIGENES = [
    "Clientify - Instagram",
    "Clientify - Whatsapp",
    "Clientify - Facebook",
    "Referido cliente activo - Redes",
    "Llamada Entrante",
    "Formulario de Facebook",
    "Formulario web",
    "Tiktok",
]
_PAUTA_DIRECTA_SET = {o.strip().lower() for o in PAUTA_DIRECTA_ORIGENES}

_COLUMNS = ["Año-Mes", "Canal", "Tipo", "Total cierres"]


def _extract_closures(df: pd.DataFrame, date_col: str, tipo: str) -> pd.DataFrame:
    """Devuelve un DataFrame ["Fecha", "Origen", "Tipo"] con una fila por
    cierre válido (fecha no nula) en `date_col`."""
    if date_col not in df.columns:
        return pd.DataFrame(columns=["Fecha", "Origen", "Tipo"])

    fechas = pd.to_datetime(df[date_col], format="%d/%m/%Y", errors="coerce")
    origen = df[CANAL_OFFLINE_COL] if CANAL_OFFLINE_COL in df.columns else pd.Series("", index=df.index)

    out = pd.DataFrame({"Fecha": fechas, "Origen": origen, "Tipo": tipo})
    return out.dropna(subset=["Fecha"])


def closures_by_channel_over_time(df: pd.DataFrame) -> pd.DataFrame:
    """Cierres por canal (Pauta directa vs Referidos) por Año-Mes, separados
    en Primer cierre / Segundo cierre.

    Columnas devueltas: "Año-Mes", "Canal", "Tipo", "Total cierres".
    """
    empty = pd.DataFrame(columns=_COLUMNS)
    if df.empty:
        return empty

    primero = _extract_closures(df, PRIMER_CIERRE_COL, "Primer cierre")
    segundo = _extract_closures(df, SEGUNDO_CIERRE_COL, "Segundo cierre")
    combined = pd.concat([primero, segundo], ignore_index=True)
    if combined.empty:
        return empty

    # Desde 2025 en adelante, sin fecha de corte superior — así sigue
    # sumando automáticamente los meses futuros (agosto, septiembre, años
    # siguientes) sin tener que tocar este código cada vez.
    combined = combined[combined["Fecha"].dt.year >= 2025].copy()
    if combined.empty:
        return empty

    origen_norm = combined["Origen"].fillna("").astype(str).str.strip().str.lower()
    combined["Canal"] = origen_norm.isin(_PAUTA_DIRECTA_SET).map({True: "Pauta directa", False: "Referido"})
    combined["Año-Mes"] = combined["Fecha"].dt.to_period("M").astype(str)

    grouped = (
        combined.groupby(["Año-Mes", "Canal", "Tipo"])
        .size()
        .reset_index(name="Total cierres")
    )
    return grouped.sort_values(["Año-Mes", "Canal", "Tipo"]).reset_index(drop=True)
