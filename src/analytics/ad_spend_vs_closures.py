"""Cruce de gasto mensual en pauta (Meta Ads) vs cantidad de cierres de leads
de "origen en redes/pauta" (ver `_redes_channel_mask`).

Funciones puras: reciben DataFrames, devuelven DataFrames. NO importan
Streamlit — eso vive en `src/ui/sections/ad_spend_vs_closures.py`.
"""
from __future__ import annotations

import pandas as pd

from src.analytics.ad_spend import MESES_ES, _clean_importe
from src.analytics.closures_by_channel_over_time import CANAL_OFFLINE_COL, redes_channel_mask
from src.analytics.metrics import CLOSE_DATE_COLS, valid_closure_estado_mask
from src.config.settings import (
    HONORARIOS_EQUIPO_DESDE_ANIO,
    HONORARIOS_EQUIPO_DESDE_MES,
    HONORARIOS_EQUIPO_MARKETING_USD,
    PAID_NETWORK_CHANNELS,
)

VALOR_PROCESO_COL = "Valor total del proceso"
CUOTA_INICIAL_COL = "Cuota inicial pactada"

# Cada etapa de cierre tiene su PROPIO campo de valor en el Excel de
# Clientify (confirmado contra un export real, 2026-08-13f) — NO se debe
# reutilizar `VALOR_PROCESO_COL` para las etapas 2/3/4, error que subestimaba
# (o sobreestimaba, según el contacto) el ingreso mensual real.
_STAGE_VALUE_COLS = {
    "Fecha de cierre": VALOR_PROCESO_COL,
    "Fecha de segundo cierre": "Valor total segundo cierre",
    "Fecha de tercer cierre": "Valor total tercer cierre",
    "Fecha de 4to cierre": "Valor total 4to cierre",
}

# Igual que `_STAGE_VALUE_COLS`, pero para la cuota inicial — cada etapa
# tiene su propio campo de cuota inicial en el Excel real (2026-08-13g).
_STAGE_CUOTA_INICIAL_COLS = {
    "Fecha de cierre": CUOTA_INICIAL_COL,
    "Fecha de segundo cierre": "Cuota inicial segundo cierre",
    "Fecha de tercer cierre": "Cuota inicial tercer cierre",
    "Fecha de 4to cierre": "Cuota inicial 4to cierre",
}

# Orígenes usados específicamente por `revenue_cuota_inicial_from_redes_
# monthly` (alimenta la gráfica de ROAS) — NI por el costo por lead
# (`closures_from_redes_total_monthly`, usa el volumen total sin restricción
# de canal desde 2026-08-13d) NI por `revenue_from_redes_monthly` (usa el
# volumen total de redes desde 2026-08-13e). A diferencia de
# `redes_channel_mask` (que incluye Orgánico/TikTok), esta lista lo excluye
# deliberadamente: TikTok/Orgánico no tiene costo de pauta atribuible en
# `datafacturacion`, así que sumarlo al ingreso por cuota inicial comparado
# contra el gasto en Meta Ads inflaría artificialmente el ROAS.
REDES_PAGAS_ORIGENES = [
    "Clientify - Instagram",
    "Clientify - Whatsapp",
    "Clientify - Facebook",
    "Referido cliente activo - Redes",
    "Llamada Entrante",
    "Formulario de Facebook",
    "Formulario web",
]
_REDES_PAGAS_SET = {o.strip().lower() for o in REDES_PAGAS_ORIGENES}

_CLOSURES_COLUMNS = ["Año", "Mes_num", "Mes_Año", "Cierres_Redes"]
_COMBINED_COLUMNS = ["Mes_Año", "Importe", "Cierres_Redes"]
_COST_COLUMNS = ["Mes_Año", "Importe", "Cierres_Redes", "Valor_por_Lead"]
_REVENUE_COLUMNS = ["Año", "Mes_num", "Mes_Año", "Ingreso_Redes"]
_REVENUE_PLOT_COLUMNS = ["Año", "Mes_num", "Mes_Año", "Concepto", "Valor"]
_CUOTA_INICIAL_COLUMNS = ["Año", "Mes_num", "Mes_Año", "Ingreso_CuotaInicial"]
_ROAS_COLUMNS = ["Año", "Mes_num", "Mes_Año", "Importe", "Ingreso_CuotaInicial", "ROAS"]
_TOTAL_ROAS_COLUMNS = ["Año", "Mes_num", "Mes_Año", "Gasto_Total", "Ingreso_CuotaInicial", "ROAS"]


def closures_from_redes_monthly(df: pd.DataFrame, channels: set[str] | None = None) -> pd.DataFrame:
    """Cuenta cierres válidos (estado != "inactivo") de "origen en redes",
    agrupados por mes, sin ninguna restricción temporal (aplica igual a todo
    el histórico: 2024, 2025, 2026, ... y años futuros).

    Por defecto usa `closures_by_channel_over_time.redes_channel_mask` (unión
    de `MARKETING_OFFLINE_CHANNELS` + Orgánico + TikTok + "Referido cliente
    activo - Redes" — ver esa función, compartida con la sección de "Cierres
    por canal" para que ambas gráficas nunca desacuerden sobre qué cuenta
    como "redes"). Si se pasa `channels`, se usa en cambio esa lista exacta
    sobre 'Canal offline' (usado por `revenue_cuota_inicial_from_redes_
    monthly`, que necesita excluir Orgánico/TikTok por no tener costo de
    pauta atribuible, para mantener la pureza del ROAS — el costo por lead y
    el ingreso por valor total del proceso, en cambio, SÍ usan el volumen
    total sin restricción de canal, ver `closures_from_redes_total_monthly`
    / `revenue_from_redes_monthly`).

    Recorre las 4 columnas de fecha de cierre (`metrics.CLOSE_DATE_COLS` —
    1ro + 2do + 3ro + 4to) y aplica el mismo filtro de validez de estado
    (`metrics.valid_closure_estado_mask`) que usa el resto de la sección de
    Gestión Comercial (KPI "Total Cierres", `eficiencia_*`, etc.) — antes
    solo miraba Primer + Segundo cierre, no filtraba por estado, y limitaba
    el canal a un whitelist angosto (`PAUTA_DIRECTA_ORIGENES`), lo que hacía
    que el total mensual de esta gráfica no coincidiera con el consolidado
    global (p.ej. 8-9 vs. 19 cierres reales en un mes).

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Cierres_Redes".
    """
    empty = pd.DataFrame(columns=_CLOSURES_COLUMNS)
    if df.empty or CANAL_OFFLINE_COL not in df.columns:
        return empty

    valid_mask = valid_closure_estado_mask(df)
    if channels is not None:
        canal_norm_full = df[CANAL_OFFLINE_COL].fillna("").astype(str).str.strip().str.lower()
        redes_mask = canal_norm_full.isin(channels)
    else:
        redes_mask = redes_channel_mask(df)
    row_mask = valid_mask & redes_mask
    if not row_mask.any():
        return empty

    partes = []
    for date_col in CLOSE_DATE_COLS:
        if date_col not in df.columns:
            continue
        partes.append(df.loc[row_mask, [date_col]].rename(columns={date_col: "Fecha"}))
    if not partes:
        return empty

    cierres = pd.concat(partes, ignore_index=True)
    cierres["Fecha"] = pd.to_datetime(cierres["Fecha"], errors="coerce", dayfirst=True)
    cierres = cierres.dropna(subset=["Fecha"]).copy()
    if cierres.empty:
        return empty

    cierres["Año"] = cierres["Fecha"].dt.year
    cierres["Mes_num"] = cierres["Fecha"].dt.month
    cierres["Mes_Año"] = cierres["Mes_num"].map(MESES_ES) + " " + cierres["Año"].astype(str)

    grouped = (
        cierres.groupby(["Año", "Mes_num", "Mes_Año"])
        .size()
        .reset_index(name="Cierres_Redes")
        .sort_values(["Año", "Mes_num"])
    )
    return grouped.reset_index(drop=True)


def closures_from_redes_total_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Denominador del costo promedio por lead de redes (gráfica "Gasto en
    pauta vs. Costo promedio por lead de redes").

    Regla de negocio (2026-08-13d, reemplaza la restricción anterior a
    `REDES_PAGAS_ORIGENES`): el costo por lead se calcula dividiendo el
    gasto en Meta Ads entre el VOLUMEN TOTAL de cierres de redes — incluido
    Orgánico/TikTok/"Referido cliente activo - Redes" — no solo los canales
    con costo de pauta directamente atribuible. Es simplemente
    `closures_from_redes_monthly` sin restricción de canal (usa
    `redes_channel_mask` por defecto).

    IMPORTANTE: `revenue_cuota_inicial_from_redes_monthly` (alimenta la
    gráfica de ROAS) sigue restringida a `REDES_PAGAS_ORIGENES` a propósito,
    para mantener la pureza del cálculo de ROAS (ingreso solo de canales con
    gasto en Meta atribuible). `revenue_from_redes_monthly` (valor total del
    proceso, gráfica "Gasto en pauta vs Ingresos por redes") en cambio SÍ
    usa el volumen total desde 2026-08-13e — ver esa función."""
    return closures_from_redes_monthly(df)


def combine_ad_spend_and_closures(
    gasto_mensual: pd.DataFrame, cierres_redes_mensual: pd.DataFrame
) -> pd.DataFrame:
    """Cruza el gasto mensual en pauta (salida de `ad_spend.monthly_ad_spend`)
    con los cierres mensuales de redes por 'Mes_Año'.

    Left join desde `gasto_mensual`: solo se grafican los meses con gasto
    registrado (el orden cronológico de `gasto_mensual` se conserva); un mes
    con gasto pero sin cierres de redes queda en 0, no se descarta.

    Columnas devueltas: "Mes_Año", "Importe", "Cierres_Redes".
    """
    if gasto_mensual.empty:
        return pd.DataFrame(columns=_COMBINED_COLUMNS)

    cierres = (
        cierres_redes_mensual[["Mes_Año", "Cierres_Redes"]]
        if not cierres_redes_mensual.empty
        else pd.DataFrame(columns=["Mes_Año", "Cierres_Redes"])
    )
    merged = gasto_mensual.merge(cierres, on="Mes_Año", how="left")
    merged["Cierres_Redes"] = merged["Cierres_Redes"].fillna(0).astype(int)
    return merged[_COMBINED_COLUMNS]


def combine_ad_spend_and_cost_per_lead(
    gasto_mensual: pd.DataFrame, cierres_redes_mensual: pd.DataFrame
) -> pd.DataFrame:
    """Como `combine_ad_spend_and_closures`, agregando 'Valor_por_Lead'
    (gasto / cierres de redes de ese mes; 0.0 si no hubo cierres, para no
    dividir por cero).

    Columnas devueltas: "Mes_Año", "Importe", "Cierres_Redes", "Valor_por_Lead".
    """
    combined = combine_ad_spend_and_closures(gasto_mensual, cierres_redes_mensual)
    if combined.empty:
        return pd.DataFrame(columns=_COST_COLUMNS)

    combined = combined.copy()
    combined["Valor_por_Lead"] = combined.apply(
        lambda r: r["Importe"] / r["Cierres_Redes"] if r["Cierres_Redes"] > 0 else 0.0,
        axis=1,
    )
    return combined[_COST_COLUMNS]


def revenue_from_redes_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Suma `VALOR_PROCESO_COL` ("Valor total del proceso" — el valor total
    del proceso vendido, NO la cuota inicial) de los cierres válidos (estado
    != "inactivo", 1ro + 2do + 3ro + 4to cierre) de "origen en redes",
    agrupados por mes. Alimenta la barra naranja de "Comparativo Mes-Año:
    Gasto en pauta vs Ingresos por redes".

    Regla de negocio (2026-08-13e, reemplaza la restricción anterior a
    `REDES_PAGAS_ORIGENES`): usa la misma máscara unificada de canales que
    el resto de gráficas de volumen (`closures_by_channel_over_time.
    redes_channel_mask` — `MARKETING_OFFLINE_CHANNELS` ∪ Orgánico ∪ TikTok ∪
    "Referido cliente activo - Redes"), NO el subconjunto pagado.

    IMPORTANTE: `revenue_cuota_inicial_from_redes_monthly` (alimenta la
    gráfica de ROAS, un cálculo financiero distinto) NO cambió — sigue
    restringida a `REDES_PAGAS_ORIGENES` para mantener la pureza del ROAS.

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Ingreso_Redes".
    """
    empty = pd.DataFrame(columns=_REVENUE_COLUMNS)
    if df.empty or CANAL_OFFLINE_COL not in df.columns or VALOR_PROCESO_COL not in df.columns:
        return empty

    valid_mask = valid_closure_estado_mask(df)
    row_mask = valid_mask & redes_channel_mask(df)
    if not row_mask.any():
        return empty

    partes = []
    for date_col in CLOSE_DATE_COLS:
        if date_col not in df.columns:
            continue
        partes.append(
            df.loc[row_mask, [date_col, VALOR_PROCESO_COL]].rename(columns={date_col: "Fecha"})
        )
    if not partes:
        return empty

    cierres = pd.concat(partes, ignore_index=True)
    cierres["Fecha"] = pd.to_datetime(cierres["Fecha"], errors="coerce", dayfirst=True)
    cierres = cierres.dropna(subset=["Fecha"]).copy()
    if cierres.empty:
        return empty

    cierres["Valor_num"] = cierres[VALOR_PROCESO_COL].apply(_clean_importe)
    cierres["Año"] = cierres["Fecha"].dt.year
    cierres["Mes_num"] = cierres["Fecha"].dt.month
    cierres["Mes_Año"] = cierres["Mes_num"].map(MESES_ES) + " " + cierres["Año"].astype(str)

    grouped = (
        cierres.groupby(["Año", "Mes_num", "Mes_Año"])["Valor_num"]
        .sum()
        .reset_index()
        .rename(columns={"Valor_num": "Ingreso_Redes"})
        .sort_values(["Año", "Mes_num"])
    )
    return grouped.reset_index(drop=True)


def _redes_isolated_channel_mask(df: pd.DataFrame) -> pd.Series:
    """Máscara de canal compartida ÚNICAMENTE por las funciones "aisladas"
    dedicadas a gráficas específicas (`calculate_redes_revenue_chart`
    2026-08-13f, `calculate_redes_initial_payments_chart` 2026-08-13g) — NO
    se usa en `revenue_from_redes_monthly`, `revenue_cuota_inicial_from_
    redes_monthly`, ni ninguna otra función "general" de este archivo.

    Parte de `redes_channel_mask` (`MARKETING_OFFLINE_CHANNELS` ∪ Orgánico ∪
    TikTok ∪ "Referido cliente activo - Redes") y le agrega el cruce
    `canal online == "paid social"` como señal adicional, por si algún lead
    trae ese canal online pero un 'Canal offline' que no matchea ninguna de
    las categorías anteriores (verificado contra un export real: en la
    práctica todo lead con canal online="paid social" ya venía cubierto por
    `redes_channel_mask` vía 'Canal offline', pero se deja explícito por
    robustez ante datos futuros)."""
    if df.empty or CANAL_OFFLINE_COL not in df.columns:
        return pd.Series(False, index=df.index)
    base_mask = redes_channel_mask(df)
    if "canal online" not in df.columns:
        return base_mask
    canal_online_norm = df["canal online"].fillna("").astype(str).str.strip().str.lower()
    paid_social_mask = canal_online_norm.isin(PAID_NETWORK_CHANNELS)
    return base_mask | paid_social_mask


def calculate_redes_revenue_chart(df: pd.DataFrame) -> pd.DataFrame:
    """Ingreso mensual de redes para la gráfica "Gasto en pauta vs Ingresos
    por redes" — lógica AISLADA (2026-08-13f), no comparte código de
    agregación con `revenue_from_redes_monthly` ni ninguna otra función de
    ingreso/ROAS de este archivo, a propósito, para que un ajuste futuro a
    esta gráfica nunca pueda afectar otra métrica del dashboard.

    Dos diferencias respecto a `revenue_from_redes_monthly`:

    1. **Evaluación multietapa real**: cada una de las 4 fechas de cierre
       tiene su PROPIO campo de valor en el Excel de Clientify (confirmado
       contra un export real) — `_STAGE_VALUE_COLS` mapea cada fecha a su
       campo correcto (1ro -> "Valor total del proceso", 2do -> "Valor
       total segundo cierre", 3ro -> "Valor total tercer cierre", 4to ->
       "Valor total 4to cierre"). `revenue_from_redes_monthly` reutiliza
       "Valor total del proceso" para las 4 fechas, lo cual es incorrecto.
    2. **Máscara de canal ampliada**: usa `_redes_isolated_channel_mask`
       (agrega el cruce canal online == "paid social").

    Mismo filtro de validez de estado que el resto de Gestión Comercial
    (`valid_closure_estado_mask`, estado != "inactivo").

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Ingreso_Redes".
    """
    empty = pd.DataFrame(columns=_REVENUE_COLUMNS)
    value_cols_presentes = [c for c in _STAGE_VALUE_COLS.values() if c in df.columns]
    if df.empty or CANAL_OFFLINE_COL not in df.columns or not value_cols_presentes:
        return empty

    valid_mask = valid_closure_estado_mask(df)
    row_mask = valid_mask & _redes_isolated_channel_mask(df)
    if not row_mask.any():
        return empty

    partes = []
    for date_col, value_col in _STAGE_VALUE_COLS.items():
        if date_col not in df.columns or value_col not in df.columns:
            continue
        partes.append(
            df.loc[row_mask, [date_col, value_col]].rename(
                columns={date_col: "Fecha", value_col: "Valor_raw"}
            )
        )
    if not partes:
        return empty

    cierres = pd.concat(partes, ignore_index=True)
    cierres["Fecha"] = pd.to_datetime(cierres["Fecha"], errors="coerce", dayfirst=True)
    cierres = cierres.dropna(subset=["Fecha"]).copy()
    if cierres.empty:
        return empty

    cierres["Valor_num"] = cierres["Valor_raw"].apply(_clean_importe)
    cierres["Año"] = cierres["Fecha"].dt.year
    cierres["Mes_num"] = cierres["Fecha"].dt.month
    cierres["Mes_Año"] = cierres["Mes_num"].map(MESES_ES) + " " + cierres["Año"].astype(str)

    grouped = (
        cierres.groupby(["Año", "Mes_num", "Mes_Año"])["Valor_num"]
        .sum()
        .reset_index()
        .rename(columns={"Valor_num": "Ingreso_Redes"})
        .sort_values(["Año", "Mes_num"])
    )
    return grouped.reset_index(drop=True)


def calculate_redes_initial_payments_chart(df: pd.DataFrame) -> pd.DataFrame:
    """Ingreso mensual por CUOTA INICIAL de redes para la gráfica "Gasto
    total (pauta + honorarios) vs Ingresos por cuota inicial (redes) y
    ROAS" (`src/ui/sections/ad_spend_total_roas.py`) — lógica AISLADA
    (2026-08-13g), no comparte código de agregación con
    `revenue_cuota_inicial_from_redes_monthly` ni ninguna otra función de
    ingreso/ROAS "general" de este archivo, a propósito, para que un ajuste
    futuro a esta gráfica nunca pueda afectar otra métrica del dashboard
    (incluida la OTRA gráfica de ROAS, `src/ui/sections/ad_spend_roas.py`,
    que sigue usando `revenue_cuota_inicial_from_redes_monthly` sin cambios).

    Dos diferencias respecto a `revenue_cuota_inicial_from_redes_monthly`:

    1. **Evaluación multietapa universal**: cada una de las 4 fechas de
       cierre tiene su PROPIO campo de cuota inicial en el Excel de
       Clientify (`_STAGE_CUOTA_INICIAL_COLS` — 1ro -> "Cuota inicial
       pactada", 2do -> "Cuota inicial segundo cierre", 3ro -> "Cuota
       inicial tercer cierre", 4to -> "Cuota inicial 4to cierre"), evaluadas
       de forma independiente: si la fecha de esa etapa cae en un mes dado,
       se suma la cuota de ESA etapa (no la del primer cierre reutilizada).
       Aplica igual a todo el histórico y a cualquier mes futuro, sin
       recorte por fecha (el corte "desde enero 2025" lo aplica
       `combine_ad_spend_total_revenue_and_roas` más abajo, no esta función).
    2. **Máscara de canal ampliada**: usa `_redes_isolated_channel_mask`
       (`MARKETING_OFFLINE_CHANNELS` ∪ Orgánico ∪ TikTok ∪ "Referido cliente
       activo - Redes" ∪ canal online == "paid social").

    Mismo filtro de validez de estado que el resto de Gestión Comercial
    (`valid_closure_estado_mask`, estado != "inactivo"). El ROAS mensual se
    recalcula automáticamente al pasar la salida de esta función como
    `ingreso_mensual` a `combine_ad_spend_total_revenue_and_roas` — esa
    función ya divide Ingreso_CuotaInicial / Gasto_Total por mes, sin
    necesidad de tocarla.

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Ingreso_CuotaInicial".
    """
    empty = pd.DataFrame(columns=_CUOTA_INICIAL_COLUMNS)
    value_cols_presentes = [c for c in _STAGE_CUOTA_INICIAL_COLS.values() if c in df.columns]
    if df.empty or CANAL_OFFLINE_COL not in df.columns or not value_cols_presentes:
        return empty

    valid_mask = valid_closure_estado_mask(df)
    row_mask = valid_mask & _redes_isolated_channel_mask(df)
    if not row_mask.any():
        return empty

    partes = []
    for date_col, value_col in _STAGE_CUOTA_INICIAL_COLS.items():
        if date_col not in df.columns or value_col not in df.columns:
            continue
        partes.append(
            df.loc[row_mask, [date_col, value_col]].rename(
                columns={date_col: "Fecha", value_col: "Valor_raw"}
            )
        )
    if not partes:
        return empty

    cierres = pd.concat(partes, ignore_index=True)
    cierres["Fecha"] = pd.to_datetime(cierres["Fecha"], errors="coerce", dayfirst=True)
    cierres = cierres.dropna(subset=["Fecha"]).copy()
    if cierres.empty:
        return empty

    cierres["Valor_num"] = cierres["Valor_raw"].apply(_clean_importe)
    cierres["Año"] = cierres["Fecha"].dt.year
    cierres["Mes_num"] = cierres["Fecha"].dt.month
    cierres["Mes_Año"] = cierres["Mes_num"].map(MESES_ES) + " " + cierres["Año"].astype(str)

    grouped = (
        cierres.groupby(["Año", "Mes_num", "Mes_Año"])["Valor_num"]
        .sum()
        .reset_index()
        .rename(columns={"Valor_num": "Ingreso_CuotaInicial"})
        .sort_values(["Año", "Mes_num"])
    )
    return grouped.reset_index(drop=True)


def combine_ad_spend_and_revenue(
    gasto_mensual: pd.DataFrame,
    ingreso_mensual: pd.DataFrame,
    since_year: int = 2025,
    since_month: int = 1,
) -> pd.DataFrame:
    """Cruza gasto en pauta (con Año/Mes_num, ver
    `ad_spend.monthly_ad_spend_with_period`) con ingreso de cierres de redes
    (usado con la salida de `calculate_redes_revenue_chart`, ver
    `src/ui/sections/ad_spend_vs_revenue.py`) por período. Outer join: un mes con gasto
    pero sin ingreso, o con ingreso pero sin gasto, se conserva igual (con
    0.0 en la columna faltante) — ninguno de los dos lados manda sobre el
    otro. Filtra estrictamente desde `since_year`/`since_month` en adelante
    y devuelve el resultado en formato largo (melt), listo para graficar con
    `px.bar(..., color="Concepto")`.

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Concepto", "Valor" —
    "Concepto" toma los valores "Importe" (gasto) e "Ingreso_Redes".
    """
    empty = pd.DataFrame(columns=_REVENUE_PLOT_COLUMNS)
    if gasto_mensual.empty and ingreso_mensual.empty:
        return empty

    gasto = gasto_mensual if not gasto_mensual.empty else pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Importe"])
    ingreso = (
        ingreso_mensual
        if not ingreso_mensual.empty
        else pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Ingreso_Redes"])
    )

    combined = pd.merge(gasto, ingreso, on=["Año", "Mes_num", "Mes_Año"], how="outer")
    combined["Importe"] = combined["Importe"].fillna(0.0)
    combined["Ingreso_Redes"] = combined["Ingreso_Redes"].fillna(0.0)

    combined = combined[
        (combined["Año"] > since_year)
        | ((combined["Año"] == since_year) & (combined["Mes_num"] >= since_month))
    ].copy()
    if combined.empty:
        return empty

    combined = combined.sort_values(["Año", "Mes_num"])

    plot = combined.melt(
        id_vars=["Año", "Mes_num", "Mes_Año"],
        value_vars=["Importe", "Ingreso_Redes"],
        var_name="Concepto",
        value_name="Valor",
    )
    return plot.reset_index(drop=True)


def revenue_cuota_inicial_from_redes_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Suma `CUOTA_INICIAL_COL` de los cierres válidos (estado != "inactivo",
    1ro + 2do + 3ro + 4to cierre — mismo criterio que
    `revenue_from_redes_monthly`) cuyo 'Canal offline' está en
    `REDES_PAGAS_ORIGENES` (sin TikTok, porque este ingreso se compara
    contra el gasto en Meta Ads), agrupados por mes.

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Ingreso_CuotaInicial".
    """
    empty = pd.DataFrame(columns=_CUOTA_INICIAL_COLUMNS)
    if df.empty or CANAL_OFFLINE_COL not in df.columns or CUOTA_INICIAL_COL not in df.columns:
        return empty

    valid_mask = valid_closure_estado_mask(df)
    partes = []
    for date_col in CLOSE_DATE_COLS:
        if date_col not in df.columns:
            continue
        partes.append(
            df.loc[valid_mask, [CANAL_OFFLINE_COL, date_col, CUOTA_INICIAL_COL]].rename(columns={date_col: "Fecha"})
        )
    if not partes:
        return empty

    cierres = pd.concat(partes, ignore_index=True)
    cierres["Fecha"] = pd.to_datetime(cierres["Fecha"], errors="coerce", dayfirst=True)
    cierres = cierres.dropna(subset=["Fecha"]).copy()
    if cierres.empty:
        return empty

    canal_norm = cierres[CANAL_OFFLINE_COL].fillna("").astype(str).str.strip().str.lower()
    cierres_redes = cierres[canal_norm.isin(_REDES_PAGAS_SET)].copy()
    if cierres_redes.empty:
        return empty

    cierres_redes["Ingreso_num"] = cierres_redes[CUOTA_INICIAL_COL].apply(_clean_importe)
    cierres_redes["Año"] = cierres_redes["Fecha"].dt.year
    cierres_redes["Mes_num"] = cierres_redes["Fecha"].dt.month
    cierres_redes["Mes_Año"] = cierres_redes["Mes_num"].map(MESES_ES) + " " + cierres_redes["Año"].astype(str)

    grouped = (
        cierres_redes.groupby(["Año", "Mes_num", "Mes_Año"])["Ingreso_num"]
        .sum()
        .reset_index()
        .rename(columns={"Ingreso_num": "Ingreso_CuotaInicial"})
        .sort_values(["Año", "Mes_num"])
    )
    return grouped.reset_index(drop=True)


def combine_ad_spend_revenue_and_roas(
    gasto_mensual: pd.DataFrame,
    ingreso_mensual: pd.DataFrame,
    since_year: int = 2025,
    since_month: int = 1,
) -> pd.DataFrame:
    """Cruza gasto en pauta (con Año/Mes_num, ver
    `ad_spend.monthly_ad_spend_with_period`) con ingreso por cuota inicial de
    cierres de redes (`revenue_cuota_inicial_from_redes_monthly`) por
    período, y agrega el ROAS mensual (Ingreso / Gasto). Outer join, mismo
    criterio que `combine_ad_spend_and_revenue` — ningún lado manda sobre el
    otro, un mes con solo uno de los dos datos queda en 0 en el otro. Filtra
    estrictamente desde `since_year`/`since_month` en adelante.

    'ROAS' es 0.0 cuando el gasto del mes es 0 (para no dividir por cero) —
    no cuando el ingreso es 0, que es un dato real (hubo gasto sin ingreso
    ese mes).

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Importe",
    "Ingreso_CuotaInicial", "ROAS" — formato ancho (no melt), porque el
    gráfico combina barras agrupadas con una línea de ROAS en eje
    secundario, a diferencia de `combine_ad_spend_and_revenue`.
    """
    empty = pd.DataFrame(columns=_ROAS_COLUMNS)
    if gasto_mensual.empty and ingreso_mensual.empty:
        return empty

    gasto = gasto_mensual if not gasto_mensual.empty else pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Importe"])
    ingreso = (
        ingreso_mensual
        if not ingreso_mensual.empty
        else pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Ingreso_CuotaInicial"])
    )

    combined = pd.merge(gasto, ingreso, on=["Año", "Mes_num", "Mes_Año"], how="outer")
    combined["Importe"] = combined["Importe"].fillna(0.0)
    combined["Ingreso_CuotaInicial"] = combined["Ingreso_CuotaInicial"].fillna(0.0)

    combined = combined[
        (combined["Año"] > since_year)
        | ((combined["Año"] == since_year) & (combined["Mes_num"] >= since_month))
    ].copy()
    if combined.empty:
        return empty

    combined = combined.sort_values(["Año", "Mes_num"])
    combined["ROAS"] = combined.apply(
        lambda r: (r["Ingreso_CuotaInicial"] / r["Importe"]) if r["Importe"] > 0 else 0.0,
        axis=1,
    )
    return combined[_ROAS_COLUMNS].reset_index(drop=True)


def combine_ad_spend_total_revenue_and_roas(
    gasto_mensual: pd.DataFrame,
    ingreso_mensual: pd.DataFrame,
    honorarios_fijos: float = HONORARIOS_EQUIPO_MARKETING_USD,
    since_year: int = 2025,
    since_month: int = 1,
    honorarios_since_year: int = HONORARIOS_EQUIPO_DESDE_ANIO,
    honorarios_since_month: int = HONORARIOS_EQUIPO_DESDE_MES,
) -> pd.DataFrame:
    """Como `combine_ad_spend_revenue_and_roas`, pero suma `honorarios_fijos`
    (retainer mensual del equipo, por defecto `settings.HONORARIOS_EQUIPO_
    MARKETING_USD` — ~$3,485.44 USD) al gasto en pauta para obtener
    'Gasto_Total', y calcula el ROAS contra ese costo operativo total (pauta
    + honorarios) en vez de solo la inversión publicitaria.

    El honorario NO se aplica retroactivamente a todo el histórico (pedido
    2026-08-14): solo se suma a partir de `honorarios_since_year`/
    `honorarios_since_month` (por defecto julio 2026, ver `settings.
    HONORARIOS_EQUIPO_DESDE_ANIO`/`_MES`) en adelante, evaluado por mes de
    forma dinámica sobre 'Año'/'Mes_num' de `gasto_mensual`. Meses previos a
    ese corte quedan con 'Gasto_Total' = solo pauta (`Importe`), igual que
    `combine_ad_spend_revenue_and_roas`.

    Los honorarios (cuando aplican por fecha) se suman ANTES del outer join,
    solo sobre los meses que sí tienen fila de gasto en pauta (`gasto_
    mensual`) — un mes que solo tenga ingreso de redes pero ningún gasto en
    pauta registrado ese período no incorpora el honorario y queda con
    'Gasto_Total' = 0 (mismo comportamiento que si no hubiera datos de gasto
    ahí, consistente con `combine_ad_spend_revenue_and_roas`). Esto es
    intencional: el honorario solo tiene sentido atribuido a un mes con
    actividad de pauta registrada.

    Usada con `ingreso_mensual` = salida de `calculate_redes_initial_payments_
    chart` (ver `src/ui/sections/ad_spend_total_roas.py`, 2026-08-13g) — el
    filtro "desde `since_year`/`since_month`" (por defecto enero 2025) lo
    aplica ESTA función, no la de ingreso, así que cubre todo el histórico y
    cualquier mes futuro automáticamente. El ROAS se recalcula solo, mes a
    mes, contra el 'Gasto_Total' resultante (con o sin honorario según
    corresponda).

    Columnas devueltas: "Año", "Mes_num", "Mes_Año", "Gasto_Total",
    "Ingreso_CuotaInicial", "ROAS".
    """
    empty = pd.DataFrame(columns=_TOTAL_ROAS_COLUMNS)
    if gasto_mensual.empty and ingreso_mensual.empty:
        return empty

    if not gasto_mensual.empty:
        gasto = gasto_mensual.copy()
        honorarios_aplica = (gasto["Año"] > honorarios_since_year) | (
            (gasto["Año"] == honorarios_since_year) & (gasto["Mes_num"] >= honorarios_since_month)
        )
        gasto["Gasto_Total"] = gasto["Importe"] + honorarios_aplica.astype(float) * honorarios_fijos
    else:
        gasto = pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Gasto_Total"])

    ingreso = (
        ingreso_mensual
        if not ingreso_mensual.empty
        else pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Ingreso_CuotaInicial"])
    )

    combined = pd.merge(
        gasto[["Año", "Mes_num", "Mes_Año", "Gasto_Total"]],
        ingreso[["Año", "Mes_num", "Mes_Año", "Ingreso_CuotaInicial"]],
        on=["Año", "Mes_num", "Mes_Año"],
        how="outer",
    )
    combined["Gasto_Total"] = combined["Gasto_Total"].fillna(0.0)
    combined["Ingreso_CuotaInicial"] = combined["Ingreso_CuotaInicial"].fillna(0.0)

    combined = combined[
        (combined["Año"] > since_year)
        | ((combined["Año"] == since_year) & (combined["Mes_num"] >= since_month))
    ].copy()
    if combined.empty:
        return empty

    combined = combined.sort_values(["Año", "Mes_num"])
    combined["ROAS"] = combined.apply(
        lambda r: (r["Ingreso_CuotaInicial"] / r["Gasto_Total"]) if r["Gasto_Total"] > 0 else 0.0,
        axis=1,
    )
    return combined[_TOTAL_ROAS_COLUMNS].reset_index(drop=True)
