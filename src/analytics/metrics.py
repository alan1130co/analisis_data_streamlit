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
    ORGANICO_OFFLINE_CHANNELS,
    ORGANICO_PAUTA_ORIGINS,
    TIKTOK_OFFLINE_CHANNELS,
    TIKTOK_PAUTA_ORIGINS,
    CIERRE_VALID_ESTADOS,
    NON_COMMERCIAL_OWNERS,
    CESAR_AUGUSTO_PREFIX,
)

CLOSE_DATE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]


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

    # --- Tarjetas principales (nueva estructura) ---
    leads_pauta: int
    leads_organico: int
    leads_tiktok: int
    asignados: int
    asignados_pauta: int
    calificados: int
    no_calificados: int
    total_cierres: int              # Solo Pauta + Orgánico, válidos, suma 1+2+3+4
    eficiencia_pauta: float
    eficiencia_bruta: float

    # --- Usados por comparación / gráficas / secciones de detalle ---
    total_cierres_general: int      # Todas las fuentes, válidos, suma 1+2+3+4
    cierres_marketing: int          # Pauta, válidos, suma 1+2+3+4
    cierres_referidos: int          # Referidos, válidos, suma 1+2+3+4

    # --- Campos legados (compatibilidad con secciones/tests existentes) ---
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
    pct_calificacion: float
    eficiencia_total: float
    eficiencia_referido: float
    eficiencia_comerciales: float
    leads_redes: int
    cierres_redes: int
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


def _is_active_estado(row) -> bool:
    """True si el `estado` del lead está en CIERRE_VALID_ESTADOS.

    Un cierre solo es válido si el lead está Activo (o Activo - mora):
    si el proceso se marcó inactivo/sin interés, el cierre no debe contarse.
    """
    estado = _safe_str(row.get("estado", "")).strip().lower()
    return estado in CIERRE_VALID_ESTADOS


def is_tiktok(row) -> bool:
    """True si el lead viene de TikTok (Canal offline u Origen de la pauta)."""
    canal_off = _safe_str(row.get("Canal offline", "")).strip().lower()
    if canal_off in TIKTOK_OFFLINE_CHANNELS:
        return True
    origen = _safe_str(row.get("Origen de la pauta", "")).strip().lower()
    return any(src in origen for src in TIKTOK_PAUTA_ORIGINS)


def is_organico(row) -> bool:
    """True si el lead es Orgánico (Canal offline u Origen de la pauta), excluyendo TikTok."""
    if is_tiktok(row):
        return False
    canal_off = _safe_str(row.get("Canal offline", "")).strip().lower()
    if canal_off in ORGANICO_OFFLINE_CHANNELS:
        return True
    origen = _safe_str(row.get("Origen de la pauta", "")).strip().lower()
    return any(src in origen for src in ORGANICO_PAUTA_ORIGINS)


def is_cesar_augusto(row) -> bool:
    """True si el propietario del lead es Cesar Augusto (único con ese nombre en el sistema)."""
    propietario = _safe_str(row.get("propietario", "")).strip().lower()
    return propietario.startswith(CESAR_AUGUSTO_PREFIX)


def is_asesor_comercial(propietario) -> bool:
    """True si `propietario` corresponde a un Asesor Comercial (excluye cuentas no comerciales)."""
    if pd.isna(propietario):
        return False
    p = str(propietario).strip().lower()
    if not p or p in {"nan", "none"}:
        return False
    return p not in NON_COMMERCIAL_OWNERS


def _is_paid_network(row) -> bool:
    """Determina si un lead viene de pauta paga (Facebook/Instagram ads).

    Señal autoritativa: el campo "Origen de la pauta" es más confiable que
    "canal online", porque los anuncios de Click-to-Message (Meta) llegan
    con canal online="inbox-referral" aunque el origen real sea pauta paga.
    """
    canal = _safe_str(row.get("canal online", "")).strip().lower()
    if canal in PAID_NETWORK_CHANNELS:
        return True
    origen = _safe_str(row.get("Origen de la pauta", "")).strip().lower()
    if not origen or origen in {"nan", "no aplica", "sin definir", ""}:
        return False
    # El campo puede venir como "Facebook" o como "['Facebook']"
    return any(src in origen for src in PAID_NETWORK_SOURCES)


def _origen_pauta_facebook_instagram(row) -> bool:
    """True únicamente si "Origen de la pauta" menciona explícitamente Facebook/Instagram.

    A diferencia de `_is_paid_network`, NO se apoya en "canal online"=="paid
    social" (ese campo por sí solo no basta como señal autoritativa: ~2700
    leads reales tienen canal online=paid social con Canal offline y Origen
    de la pauta vacíos, y deben seguir siendo Referido).
    """
    origen = _safe_str(row.get("Origen de la pauta", "")).strip().lower()
    if not origen or origen in {"nan", "no aplica", "sin definir", ""}:
        return False
    return any(src in origen for src in PAID_NETWORK_SOURCES)


def is_marketing(row) -> bool:
    """Devuelve True si el lead pertenece a Pauta (marketing pago), sin incluir
    TikTok, Orgánico ni Referidos (categorías separadas)."""
    canal_off = _safe_str(row.get("Canal offline", "")).strip().lower()
    canal_on = _safe_str(row.get("canal online", "")).strip().lower()

    # TikTok y Orgánico son categorías propias, no Pauta.
    if is_tiktok(row) or is_organico(row):
        return False

    # Canal offline que empiece con "referido" → SIEMPRE Referido, incluso si
    # trae la palabra "redes" (p.ej. "Referido cliente activo - Redes").
    if canal_off.startswith(REFERIDO_PREFIX):
        return False

    # Origen de la pauta con Facebook/Instagram es señal autoritativa de Pauta
    # (cubre leads de Click-to-Message que llegan con canal online=inbox-referral).
    if _origen_pauta_facebook_instagram(row):
        return True

    if not canal_off or canal_off in {"nan", "none"}:
        return False
    if canal_on in REFERRAL_ONLINE_CHANNELS:
        return False
    if canal_off in MARKETING_OFFLINE_CHANNELS:
        return True
    if canal_on in PAID_NETWORK_CHANNELS:
        return True
    return False


def valid_closure_event_mask(df: pd.DataFrame, date_col: str, year: int, month: int) -> pd.Series:
    """Máscara booleana: True si `date_col` cae en (year, month) Y el lead está Activo."""
    if date_col not in df.columns or df.empty:
        return pd.Series(False, index=df.index)
    s = pd.to_datetime(df[date_col], errors="coerce")
    in_month = (s.dt.year == year) & (s.dt.month == month)
    active = df.apply(_is_active_estado, axis=1)
    return in_month & active


def _sum_valid_closures(
    df_full: pd.DataFrame, year: int, month: int, predicate=None
) -> int:
    """Suma cierres válidos (Activo) del mes en las 4 columnas de fecha de cierre,
    opcionalmente filtrados por `predicate(row) -> bool`."""
    total = 0
    for col in CLOSE_DATE_COLS:
        mask = valid_closure_event_mask(df_full, col, year, month)
        if not mask.any():
            continue
        sub = df_full[mask]
        if predicate is not None:
            sub = sub[sub.apply(predicate, axis=1)]
        total += len(sub)
    return total


def _count_closures_in_month(df: pd.DataFrame, date_col: str, year: int, month: int) -> int:
    """Cuenta cuántos cierres tienen su fecha dentro del mes indicado (sin filtrar Activo).

    Se conserva para compatibilidad con el desglose crudo por etapa (1er/2do/3er/4to).
    """
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

    Embudo comercial estricto: Asignados -> Calificados -> Cierres.
    Asignados = leads con `propietario` que es Asesor Comercial.
    Calificados/No calificados se calculan SOLO sobre el universo de Asignados.
    """
    if df_full is None:
        df_full = df_period

    if df_period.empty:
        return Metrics(
            creados=0,
            leads_pauta=0, leads_organico=0, leads_tiktok=0,
            asignados=0, asignados_pauta=0,
            calificados=0, no_calificados=0,
            total_cierres=0,
            eficiencia_pauta=0.0, eficiencia_bruta=0.0,
            total_cierres_general=0, cierres_marketing=0, cierres_referidos=0,
            no_calificados_pauta=0, no_calificados_referido=0,
            creados_pauta=0, creados_referido=0,
            calificados_pauta=0, calificados_referido=0,
            cierres_por_pautas=0,
            cierres_1=0, cierres_2=0, cierres_3=0, cierres_4=0,
            cierres_adicionales=0,
            pct_calificacion=0.0,
            eficiencia_total=0.0,
            eficiencia_referido=0.0,
            eficiencia_comerciales=0.0,
            leads_redes=0, cierres_redes=0,
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

    # --- Clasificación de leads del período ---
    creados = len(df_period)

    mkt_mask = df_period.apply(is_marketing, axis=1)
    tiktok_mask = df_period.apply(is_tiktok, axis=1)
    organico_mask = df_period.apply(is_organico, axis=1)
    cesar_mask = df_period.apply(is_cesar_augusto, axis=1)
    active_mask = df_period.apply(_is_active_estado, axis=1)
    cesar_no_activo_mask = cesar_mask & ~active_mask

    # "Leads generales" de Orgánico/TikTok excluyen a César Augusto: sus leads
    # solo entran vía el filtro específico (no activos, clasificados por canal real).
    organico_generales_mask = organico_mask & ~cesar_mask
    tiktok_generales_mask = tiktok_mask & ~cesar_mask
    cesar_organico_mask = cesar_no_activo_mask & organico_mask
    cesar_tiktok_mask = cesar_no_activo_mask & tiktok_mask

    leads_pauta = int(mkt_mask.sum())
    leads_organico = int((organico_generales_mask | cesar_organico_mask).sum())
    leads_tiktok = int((tiktok_generales_mask | cesar_tiktok_mask).sum())

    # --- Asignados: solo Asesores Comerciales ---
    if "propietario" in df_period.columns:
        asignado_mask = df_period["propietario"].apply(is_asesor_comercial)
    else:
        asignado_mask = pd.Series(False, index=df_period.index)
    df_asignados = df_period[asignado_mask]
    asignados = int(asignado_mask.sum())
    asignados_pauta = int((asignado_mask & mkt_mask).sum())

    # --- Embudo estricto: Calificados/No calificados sobre Asignados ---
    calificados = int(is_qualified_mask(df_asignados).sum()) if not df_asignados.empty else 0
    no_calificados = asignados - calificados

    # --- Cierres válidos (Activo), sumando las 4 columnas, sobre el dataset completo ---
    cierres_marketing = _sum_valid_closures(df_full, year, month, is_marketing)
    cierres_organico_valid = _sum_valid_closures(df_full, year, month, is_organico)
    cierres_tiktok_valid = _sum_valid_closures(df_full, year, month, is_tiktok)

    def _is_referido(row) -> bool:
        return not (is_marketing(row) or is_organico(row) or is_tiktok(row))

    cierres_referidos = _sum_valid_closures(df_full, year, month, _is_referido)

    total_cierres = cierres_marketing + cierres_organico_valid
    total_cierres_general = (
        cierres_marketing + cierres_organico_valid + cierres_tiktok_valid + cierres_referidos
    )

    # --- Eficiencias (fórmulas exactas) ---
    eficiencia_pauta = (cierres_marketing * 100 / asignados_pauta) if asignados_pauta else 0.0
    denom_bruta = asignados_pauta + leads_organico + leads_tiktok + calificados + no_calificados
    eficiencia_bruta = (total_cierres * 100 / denom_bruta) if denom_bruta else 0.0

    # --- Campos legados (mantener para compatibilidad con secciones/tests que ya existen) ---
    df_mkt = df_period[mkt_mask]
    df_ref = df_period[~mkt_mask]
    creados_pauta = len(df_mkt)
    creados_referido = len(df_ref)
    calificados_pauta = int(is_qualified_mask(df_mkt).sum())
    calificados_referido = int(is_qualified_mask(df_ref).sum())
    no_calificados_pauta = creados_pauta - calificados_pauta
    no_calificados_referido = creados_referido - calificados_referido

    cierres_1 = int(valid_closure_event_mask(df_full, "Fecha de cierre", year, month).sum())
    cierres_2 = int(valid_closure_event_mask(df_full, "Fecha de segundo cierre", year, month).sum())
    cierres_3 = int(valid_closure_event_mask(df_full, "Fecha de tercer cierre", year, month).sum())
    cierres_4 = int(valid_closure_event_mask(df_full, "Fecha de 4to cierre", year, month).sum())
    cierres_adicionales = cierres_2 + cierres_3 + cierres_4

    paid_mask_full = df_full.apply(_is_paid_network, axis=1)
    df_paid_full = df_full[paid_mask_full]
    cierres_por_pautas = sum(
        int(valid_closure_event_mask(df_paid_full, col, year, month).sum())
        for col in CLOSE_DATE_COLS
    )

    es_pauta = df_period.apply(_is_paid_network, axis=1)
    leads_redes = int(es_pauta.sum())
    cierres_redes = cierres_por_pautas

    pct_calificacion = (calificados / asignados) if asignados else 0.0
    eficiencia_total = (total_cierres_general / calificados) if calificados else 0.0
    eficiencia_comerciales = (cierres_redes / leads_redes) if leads_redes else 0.0

    if "Fecha de cierre" in df_full.columns and year > 0:
        mask_1ro = valid_closure_event_mask(df_full, "Fecha de cierre", year, month)
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

    _adicional_cols = [
        "Fecha de segundo cierre",
        "Fecha de tercer cierre",
        "Fecha de 4to cierre",
    ]
    cierres_adicionales_pauta = 0
    cierres_adicionales_referido = 0
    for _col in _adicional_cols:
        _mask = valid_closure_event_mask(df_full, _col, year, month)
        _sub = df_full[_mask]
        if _sub.empty:
            continue
        _is_mkt = _sub.apply(is_marketing, axis=1)
        cierres_adicionales_pauta += int(_is_mkt.sum())
        cierres_adicionales_referido += int((~_is_mkt).sum())

    eficiencia_referido = (cierres_referidos / calificados_referido) if calificados_referido else 0.0

    return Metrics(
        creados=creados,
        leads_pauta=leads_pauta, leads_organico=leads_organico, leads_tiktok=leads_tiktok,
        asignados=asignados, asignados_pauta=asignados_pauta,
        calificados=calificados, no_calificados=no_calificados,
        total_cierres=total_cierres,
        eficiencia_pauta=eficiencia_pauta, eficiencia_bruta=eficiencia_bruta,
        total_cierres_general=total_cierres_general,
        cierres_marketing=cierres_marketing, cierres_referidos=cierres_referidos,
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
        pct_calificacion=pct_calificacion,
        eficiencia_total=eficiencia_total,
        eficiencia_referido=eficiencia_referido,
        eficiencia_comerciales=eficiencia_comerciales,
        leads_redes=leads_redes,
        cierres_redes=cierres_redes,
        cierres_pauta_primer=cierres_pauta_primer,
        cierres_referido_primer=cierres_referido_primer,
        cierres_adicionales_pauta=cierres_adicionales_pauta,
        cierres_adicionales_referido=cierres_adicionales_referido,
    )
