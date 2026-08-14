"""Cierres por canal (Pauta directa vs Referidos), discriminados por Primer,
Segundo, Tercer y Cuarto Cierre, a lo largo del tiempo (Año-Mes).

Funciones puras: reciben DataFrame, devuelven DataFrame.
NO importan Streamlit ni nada de la UI.
"""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import get_mask, is_organico, is_tiktok
from src.config.settings import MARKETING_OFFLINE_CHANNELS

CANAL_OFFLINE_COL = "Canal offline"
PRIMER_CIERRE_COL = "Fecha de cierre"
SEGUNDO_CIERRE_COL = "Fecha de segundo cierre"
TERCER_CIERRE_COL = "Fecha de tercer cierre"
CUARTO_CIERRE_COL = "Fecha de 4to cierre"

# Mapa Tipo -> columna de fecha, en el orden en que deben apilarse las
# barras (pedido 2026-08-14: antes solo Primer + Segundo, ahora las 4
# etapas de cierre — mismas columnas que `metrics.CLOSE_DATE_COLS`).
_TIPO_COLS = {
    "Primer cierre": PRIMER_CIERRE_COL,
    "Segundo cierre": SEGUNDO_CIERRE_COL,
    "Tercer cierre": TERCER_CIERRE_COL,
    "Cuarto cierre": CUARTO_CIERRE_COL,
}

# Origen adicional que cuenta como "redes" SOLO para las gráficas de
# volumen/conteo de cierres (esta y `ad_spend_vs_closures.
# closures_from_redes_monthly`) — no para las métricas financieras
# (revenue/CPL/ROAS en `ad_spend_vs_closures.py`), que siguen su propia
# lista `REDES_PAGAS_ORIGENES`.
_REFERIDO_REDES_ORIGEN = "referido cliente activo - redes"

_COLUMNS = ["Año-Mes", "Canal", "Tipo", "Total cierres"]


def redes_channel_mask(df: pd.DataFrame) -> pd.Series:
    """Máscara fila por fila (sin ninguna restricción temporal — aplica
    idéntica a 2024, 2025, 2026, ... y a cualquier año futuro) de qué leads
    cuentan como "origen en redes/pauta directa".

    Unión ESTRICTA de:
    - `settings.MARKETING_OFFLINE_CHANNELS` (comparación exacta sobre
      'Canal offline'): Clientify - Facebook/Instagram/Whatsapp, Formulario
      de Facebook - cliente potencial, Formulario web, Llamada Entrante.
    - Orgánico + TikTok (`metrics.is_organico` / `metrics.is_tiktok` — misma
      lógica de clasificación que usa el resto de la app, ya cubre tanto
      'Canal offline' como 'Origen de la pauta').
    - `"Referido cliente activo - Redes"` (comparación exacta sobre 'Canal
      offline') — un referido puntual, no orgánico ni pauta paga, que el
      negocio igual cuenta como "redes" para el CONTEO de cierres. Solo
      afecta esta máscara de volumen, no las métricas financieras.

    Cualquier otro valor cae en "Referido". Compartida por esta gráfica y
    por `ad_spend_vs_closures.closures_from_redes_monthly` para que ninguna
    de las dos pueda desacordar sobre qué cuenta como "redes" — antes cada
    una tenía su propio whitelist angosto (`PAUTA_DIRECTA_ORIGENES`), que
    subcontaba el histórico completo.
    """
    if df.empty or CANAL_OFFLINE_COL not in df.columns:
        return pd.Series(False, index=df.index)
    canal_norm = df[CANAL_OFFLINE_COL].fillna("").astype(str).str.strip().str.lower()
    marketing_mask = canal_norm.isin(MARKETING_OFFLINE_CHANNELS)
    organico_mask = get_mask(df, "_is_organico", is_organico)
    tiktok_mask = get_mask(df, "_is_tiktok", is_tiktok)
    referido_redes_mask = canal_norm == _REFERIDO_REDES_ORIGEN
    return marketing_mask | organico_mask | tiktok_mask | referido_redes_mask


def _extract_closures(df: pd.DataFrame, date_col: str, tipo: str, redes_mask: pd.Series) -> pd.DataFrame:
    """Devuelve un DataFrame ["Fecha", "EsRedes", "Tipo"] con una fila por
    cierre válido (fecha no nula) en `date_col`."""
    if date_col not in df.columns:
        # dtype explícito en "Fecha" (datetime64, no object) — si no, cuando
        # solo algunas de las 4 columnas de cierre están presentes en `df`,
        # el `pd.concat` en `closures_by_channel_over_time` mezcla una
        # columna datetime64 real con esta vacía de dtype object y degrada
        # todo el resultado a object, rompiendo el `.dt` accessor más abajo.
        return pd.DataFrame({
            "Fecha": pd.Series(dtype="datetime64[ns]"),
            "EsRedes": pd.Series(dtype=bool),
            "Tipo": pd.Series(dtype=object),
        })

    fechas = pd.to_datetime(df[date_col], format="%d/%m/%Y", errors="coerce")

    out = pd.DataFrame({"Fecha": fechas, "Tipo": tipo}, index=df.index)
    out["EsRedes"] = redes_mask
    return out.dropna(subset=["Fecha"])


def closures_by_channel_over_time(df: pd.DataFrame) -> pd.DataFrame:
    """Cierres por canal (Pauta directa vs Referidos) por Año-Mes, separados
    en Primer / Segundo / Tercer / Cuarto cierre (pedido 2026-08-14: antes
    solo cubría Primer + Segundo).

    Columnas devueltas: "Año-Mes", "Canal", "Tipo", "Total cierres".
    """
    empty = pd.DataFrame(columns=_COLUMNS)
    if df.empty:
        return empty

    redes_mask = redes_channel_mask(df)
    partes = [
        _extract_closures(df, date_col, tipo, redes_mask)
        for tipo, date_col in _TIPO_COLS.items()
    ]
    combined = pd.concat(partes, ignore_index=True)
    if combined.empty:
        return empty

    # Desde 2025 en adelante, sin fecha de corte superior — así sigue
    # sumando automáticamente los meses futuros (agosto, septiembre, años
    # siguientes) sin tener que tocar este código cada vez.
    combined = combined[combined["Fecha"].dt.year >= 2025].copy()
    if combined.empty:
        return empty

    combined["Canal"] = combined["EsRedes"].map({True: "Pauta directa", False: "Referido"})
    combined["Año-Mes"] = combined["Fecha"].dt.to_period("M").astype(str)

    grouped = (
        combined.groupby(["Año-Mes", "Canal", "Tipo"])
        .size()
        .reset_index(name="Total cierres")
    )
    return grouped.sort_values(["Año-Mes", "Canal", "Tipo"]).reset_index(drop=True)
