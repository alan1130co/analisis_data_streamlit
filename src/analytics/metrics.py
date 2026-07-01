"""
Cálculo de KPIs para el dashboard.

Todas las funciones reciben DataFrames y devuelven números o dicts.
NO importan Streamlit ni nada de la UI.
"""
from dataclasses import dataclass, asdict

import pandas as pd

from src.config.settings import (
    QUALIFIED_MOTIVES,
    MARKETING_OFFLINE_CHANNELS,
    REFERIDO_PREFIX,
    REFERRAL_ONLINE_CHANNELS,
    PAID_NETWORK_CHANNELS,
    PAID_NETWORK_SOURCES,
)


def is_qualified_mask(df: pd.DataFrame) -> pd.Series:
    """
    Máscara booleana: True si el lead está calificado.

    Calificado si cualquiera de estas condiciones se cumple:
      - Motivo de no cierre está en QUALIFIED_MOTIVES
      - Cantidad de cierres >= 1
      - Motivo está vacío / None / 'nan' / 'sin diligenciar' (aún sin clasificar)

    Solo es NO calificado si el motivo está EXPLÍCITAMENTE en UNQUALIFIED_MOTIVES.
    """
    if df.empty:
        return pd.Series([], dtype=bool, index=df.index)

    if "Motivo de no cierre" in df.columns:
        motivo = df["Motivo de no cierre"].fillna("").astype(str).str.lower().str.strip()
    else:
        motivo = pd.Series([""] * len(df), index=df.index)

    if "Cantidad de cierres" in df.columns:
        cierres = df["Cantidad de cierres"].fillna(0)
    else:
        cierres = pd.Series([0.0] * len(df), index=df.index)

    mask_qualified_motive = motivo.isin(QUALIFIED_MOTIVES)
    mask_cierre = cierres >= 1
    mask_no_diligenciar = motivo.isin({"", "nan", "none", "sin diligenciar"})

    return mask_qualified_motive | mask_cierre | mask_no_diligenciar


@dataclass
class Metrics:
    """Contenedor de todos los KPIs del período."""
    creados: int
    asignados: int
    calificados: int
    no_calificados: int
    no_calificados_pauta: int
    no_calificados_referido: int
    creados_pauta: int
    creados_referido: int
    calificados_pauta: int
    calificados_referido: int
    cierres_por_pautas: int
    cierres_1: int
    cierres_2: int
    cierres_3: int
    cierres_4: int
    cierres_adicionales: int
    total_cierres: int
    pct_calificacion: float
    eficiencia_total: float
    eficiencia_pauta: float
    eficiencia_referido: float
    eficiencia_comerciales: float
    leads_redes: int
    cierres_redes: int
    cierres_marketing: int
    cierres_referidos: int
    cierres_pauta_primer: int
    cierres_referido_primer: int
    cierres_adicionales_pauta: int
    cierres_adicionales_referido: int

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_str(value) -> str:
    """Convierte un valor de celda a string, tratando NaN/None/pd.NA como ''.

    row.get(...) or "" rompe con TypeError cuando el valor es pd.NA, porque
    NAType.__bool__ no está definido para usarse en un `or`.
    """
    if pd.isna(value):
        return ""
    return str(value)


def is_marketing(row) -> bool:
    """Devuelve True si el lead pertenece al equipo de Marketing (pautas/redes)."""
    canal_off = _safe_str(row.get("Canal offline", "")).strip().lower()
    canal_on = _safe_str(row.get("canal online", "")).strip().lower()
    # Canal offline vacío → Referido
    if not canal_off or canal_off in {"nan", "none"}:
        return False
    # REGLA UNIVERSAL: canal que mencione "redes" → PAUTA (evaluada antes que "referido")
    if "redes" in canal_off:
        return True
    # Canal online inbox-referral → Referido
    if canal_on in REFERRAL_ONLINE_CHANNELS:
        return False
    # Canal offline reconocido como marketing → PAUTA
    if canal_off in MARKETING_OFFLINE_CHANNELS:
        return True
    # Canal online paid social → PAUTA
    if canal_on in PAID_NETWORK_CHANNELS:
        return True
    # "Orgánico" es PAUTA: comentario en publicación contactado proactivamente por marketing
    if canal_off in {"orgánico", "organico"}:
        return True
    # Canal offline que empiece con "referido" (sin "redes") → Referido
    if canal_off.startswith(REFERIDO_PREFIX):
        return False
    return False


def _is_paid_network(row) -> bool:
    """Determina si un lead viene de pauta paga (Facebook/Instagram ads)."""
    canal = _safe_str(row.get("canal online", "")).strip().lower()
    if canal in PAID_NETWORK_CHANNELS:
        return True
    origen = _safe_str(row.get("Origen de la pauta", "")).strip().lower()
    if not origen or origen in {"nan", "no aplica", "sin definir", ""}:
        return False
    # El campo puede venir como "Facebook" o como "['Facebook']"
    return any(src in origen for src in PAID_NETWORK_SOURCES)


def _count_closures_in_month(df: pd.DataFrame, date_col: str, year: int, month: int) -> int:
    """Cuenta cuántos cierres tienen su fecha dentro del mes indicado."""
    if date_col not in df.columns:
        return 0
    s = pd.to_datetime(df[date_col], errors="coerce")
    mask = (s.dt.year == year) & (s.dt.month == month)
    return int(mask.sum())


# ---------------------------------------------------------------------------
# Cálculo principal
# ---------------------------------------------------------------------------

def compute_all_metrics(
    df_period: pd.DataFrame,
    df_full: pd.DataFrame | None = None,
) -> Metrics:
    """
    Calcula todos los KPIs sobre los registros del período.

    `df_period` = registros creados en el mes seleccionado.
    `df_full`   = el dataset completo (necesario para contar cierres por
                  fecha de cierre, ya que un lead creado meses atrás puede
                  cerrar este mes).
    """
    if df_full is None:
        df_full = df_period

    # Si no hay datos, devolver todo en cero
    if df_period.empty:
        return Metrics(
            creados=0, asignados=0, calificados=0,
            no_calificados=0, no_calificados_pauta=0, no_calificados_referido=0,
            creados_pauta=0, creados_referido=0,
            calificados_pauta=0, calificados_referido=0,
            cierres_por_pautas=0,
            cierres_1=0, cierres_2=0, cierres_3=0, cierres_4=0,
            cierres_adicionales=0,
            total_cierres=0,
            pct_calificacion=0.0,
            eficiencia_total=0.0,
            eficiencia_pauta=0.0,
            eficiencia_referido=0.0,
            eficiencia_comerciales=0.0,
            leads_redes=0, cierres_redes=0,
            cierres_marketing=0, cierres_referidos=0,
            cierres_pauta_primer=0, cierres_referido_primer=0,
            cierres_adicionales_pauta=0, cierres_adicionales_referido=0,
        )

    # --- Período (año, mes) que estamos analizando ---
    creado_series = pd.to_datetime(df_period["creado"], errors="coerce").dropna()
    if creado_series.empty:
        year, month = 0, 0
    else:
        first = creado_series.iloc[0]
        year, month = int(first.year), int(first.month)

    # --- Métricas básicas ---
    creados = len(df_period)

    asignados = int(df_period["propietario"].notna().sum()) if "propietario" in df_period else 0

    calificados = int(is_qualified_mask(df_period).sum())
    no_calificados = len(df_period) - calificados

    mkt_period_mask = df_period.apply(is_marketing, axis=1)
    df_mkt = df_period[mkt_period_mask]
    df_ref = df_period[~mkt_period_mask]
    creados_pauta = len(df_mkt)
    creados_referido = len(df_ref)

    calificados_pauta = int(is_qualified_mask(df_mkt).sum())
    calificados_referido = int(is_qualified_mask(df_ref).sum())
    no_calificados_pauta = creados_pauta - calificados_pauta
    no_calificados_referido = creados_referido - calificados_referido

    # --- Cierres totales por mes (usando fechas de cierre, sobre el dataset completo) ---
    cierres_1 = _count_closures_in_month(df_full, "Fecha de cierre", year, month)
    cierres_2 = _count_closures_in_month(df_full, "Fecha de segundo cierre", year, month)
    cierres_3 = _count_closures_in_month(df_full, "Fecha de tercer cierre", year, month)
    cierres_4 = _count_closures_in_month(df_full, "Fecha de 4to cierre", year, month)
    cierres_adicionales = cierres_2 + cierres_3 + cierres_4
    # total_cierres = solo leads con PRIMERA fecha de cierre en el mes
    # (igual al filtro "Fecha de cierre BETWEEN" de Clientify)
    # Los adicionales (2do/3ro/4to) de meses anteriores se muestran aparte.
    total_cierres = cierres_1

    # --- Cierres por pautas: para cada columna de fecha de cierre en df_full,
    # contar cierres del mes que vienen de lead de pauta paga ---
    paid_mask_full = df_full.apply(_is_paid_network, axis=1)
    df_paid_full = df_full[paid_mask_full]
    close_date_cols = [
        "Fecha de cierre",
        "Fecha de segundo cierre",
        "Fecha de tercer cierre",
        "Fecha de 4to cierre",
    ]
    cierres_por_pautas = sum(
        _count_closures_in_month(df_paid_full, col, year, month)
        for col in close_date_cols
    )

    # --- Leads de redes (del período) y eficiencias ---
    es_pauta = df_period.apply(_is_paid_network, axis=1)
    leads_redes = int(es_pauta.sum())
    cierres_redes = cierres_por_pautas

    pct_calificacion = (calificados / asignados) if asignados else 0.0
    eficiencia_total = (total_cierres / calificados) if calificados else 0.0
    eficiencia_comerciales = (cierres_redes / leads_redes) if leads_redes else 0.0

    # --- 1er cierre del mes por equipo (solo columna "Fecha de cierre") ---
    if "Fecha de cierre" in df_full.columns and year > 0:
        fecha_1ro = pd.to_datetime(df_full["Fecha de cierre"], errors="coerce")
        mask_1ro = (fecha_1ro.dt.year == year) & (fecha_1ro.dt.month == month)
        leads_1ro = df_full[mask_1ro]
        if not leads_1ro.empty:
            is_mkt_1ro = leads_1ro.apply(is_marketing, axis=1)
            cierres_pauta_primer = int(is_mkt_1ro.sum())
            cierres_referido_primer = int((~is_mkt_1ro).sum())
        else:
            cierres_pauta_primer = 0
            cierres_referido_primer = 0
    else:
        cierres_pauta_primer = 0
        cierres_referido_primer = 0

    # --- Cierres del mes por equipo: solo 1ra fecha de cierre (consistente con total_cierres) ---
    cierres_marketing = cierres_pauta_primer
    cierres_referidos = cierres_referido_primer

    eficiencia_pauta = (cierres_marketing / calificados_pauta) if calificados_pauta else 0.0
    eficiencia_referido = (cierres_referidos / calificados_referido) if calificados_referido else 0.0

    # --- Adicionales (2do+3ro+4to) por equipo ---
    _adicional_cols = [
        "Fecha de segundo cierre",
        "Fecha de tercer cierre",
        "Fecha de 4to cierre",
    ]
    cierres_adicionales_pauta = 0
    cierres_adicionales_referido = 0
    for _col in _adicional_cols:
        if _col not in df_full.columns:
            continue
        _s = pd.to_datetime(df_full[_col], errors="coerce")
        _mask = (_s.dt.year == year) & (_s.dt.month == month)
        _sub = df_full[_mask]
        if _sub.empty:
            continue
        _is_mkt = _sub.apply(is_marketing, axis=1)
        cierres_adicionales_pauta += int(_is_mkt.sum())
        cierres_adicionales_referido += int((~_is_mkt).sum())

    return Metrics(
        creados=creados,
        asignados=asignados,
        calificados=calificados,
        no_calificados=no_calificados,
        no_calificados_pauta=no_calificados_pauta,
        no_calificados_referido=no_calificados_referido,
        creados_pauta=creados_pauta,
        creados_referido=creados_referido,
        calificados_pauta=calificados_pauta,
        calificados_referido=calificados_referido,
        cierres_por_pautas=cierres_por_pautas,
        cierres_1=cierres_1,
        cierres_2=cierres_2,
        cierres_3=cierres_3,
        cierres_4=cierres_4,
        cierres_adicionales=cierres_adicionales,
        total_cierres=total_cierres,
        pct_calificacion=pct_calificacion,
        eficiencia_total=eficiencia_total,
        eficiencia_pauta=eficiencia_pauta,
        eficiencia_referido=eficiencia_referido,
        eficiencia_comerciales=eficiencia_comerciales,
        leads_redes=leads_redes,
        cierres_redes=cierres_redes,
        cierres_marketing=cierres_marketing,
        cierres_referidos=cierres_referidos,
        cierres_pauta_primer=cierres_pauta_primer,
        cierres_referido_primer=cierres_referido_primer,
        cierres_adicionales_pauta=cierres_adicionales_pauta,
        cierres_adicionales_referido=cierres_adicionales_referido,
    )
