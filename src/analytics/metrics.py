"""
Cálculo de KPIs para el dashboard.

Todas las funciones reciben DataFrames y devuelven números o dicts.
NO importan Streamlit ni nada de la UI.
"""
import unicodedata
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
    PAUTA_REDES_TERM,
    SOCIAL_CHANNEL_TERMS,
    PAUTA_LLAMADA_TERM,
    CIERRE_INVALID_ESTADOS,
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
    leads_organico_tiktok: int       # leads_organico + leads_tiktok (tarjeta combinada)
    asignados: int
    asignados_pauta: int
    asignados_organico: int
    asignados_tiktok: int
    calificados: int
    no_calificados: int
    total_cierres: int              # = cierres_marketing (Pauta, que ya incluye TikTok/Orgánico/redes-referidos)
    eficiencia_real: float           # (Cierres de Pauta * 100) / Calificados del mes — "% Eficiencia Real"
    eficiencia_bruta: float
    eficiencia_global: float         # (Cierres de Pauta * 100) / Creados del mes — "% Eficiencia Global"

    total_cierres_estricto: int     # Suma ESTRICTA cierres_pauta_primer + cierres_referido_primer
                                     # + cierres_adicionales — usado por la tarjeta "Total Cierres"
                                     # para que SIEMPRE cuadre por construcción con las 3 tarjetas
                                     # que lo componen (Pauta M / Referidos R / Adicionales).

    # --- Usados por comparación / gráficas / secciones de detalle ---
    total_cierres_general: int      # cierres_marketing + cierres_referidos (partición binaria completa)
    cierres_marketing: int          # Pauta (2026-07-03e: incluye TikTok/Orgánico/redes-referidos), válidos, suma 1+2+3+4
    cierres_referidos: int          # Referido PURO (sin "redes" en el nombre), válidos, suma 1+2+3+4
    cierres_organico: int           # Desglose informativo: Orgánico válidos (subconjunto de cierres_marketing)
    cierres_tiktok: int             # Desglose informativo: TikTok válidos (subconjunto de cierres_marketing)
    cierres_no_pauta: int           # = cierres_referidos (alias legado; TikTok/Orgánico ya no son "no pauta")

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


def _strip_accents(value: str) -> str:
    """Quita tildes/diacríticos (César -> Cesar) para comparar de forma robusta
    sin depender de cómo haya venido acentuado el texto en el Excel."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def _is_valid_closure_estado(row) -> bool:
    """True si el `estado` del lead NO es exactamente "inactivo".

    Regla de Cierre Válido: un cierre cuenta salvo que el proceso quedó
    "inactivo" (contrato caído / dinero devuelto). Cualquier otro estado
    (activo, activo - mora, en trámite, etc.) es válido — no se exige una
    lista blanca de estados "buenos", solo se excluye el explícitamente malo.
    """
    estado = _safe_str(row.get("estado", "")).strip().lower()
    return estado not in CIERRE_INVALID_ESTADOS


def valid_closure_estado_mask(df: pd.DataFrame) -> pd.Series:
    """Versión vectorizada de `_is_valid_closure_estado`, misma regla exacta
    (estado != "inactivo"), sin iterar fila por fila.

    `_is_valid_closure_estado` se llamaba vía `.apply(..., axis=1)` sobre el
    DataFrame COMPLETO en ~17 puntos del código (metrics.py + casi todos los
    módulos de `analytics/*.py`) — cada rerun de Streamlit (p.ej. al cambiar
    el mes del filtro) repetía ese recorrido fila-por-fila decenas de veces
    sobre miles de leads, lo cual era el principal cuello de botella de
    rendimiento. Como la regla es una simple pertenencia a un set, es
    trivialmente vectorizable sin ningún riesgo de cambiar el resultado.
    """
    if df.empty or "estado" not in df.columns:
        return pd.Series(True, index=df.index)
    estado = df["estado"].apply(_safe_str).str.strip().str.lower()
    return ~estado.isin(CIERRE_INVALID_ESTADOS)


def get_mask(df: pd.DataFrame, column: str, func) -> pd.Series:
    """Devuelve la columna precomputada `column` si ya existe en `df` (ver
    `precompute_derived_columns`); si no, la calcula al vuelo con `func`
    (row-wise, vía `.apply(func, axis=1)`, comportamiento idéntico al de
    siempre — usado como fallback para DataFrames de test que no pasan por
    el pipeline de carga real).

    No reimplementa ninguna regla de negocio: solo evita recomputar
    predicados costosos (`is_marketing`, `is_tiktok`, etc.) más de una vez
    sobre el mismo DataFrame.
    """
    if column in df.columns:
        return df[column]
    if df.empty:
        return pd.Series([], dtype=bool, index=df.index)
    return df.apply(func, axis=1)


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
    """True si el propietario del lead es Cesar Augusto (único con ese nombre en el sistema).

    Comparación sin tildes: el Excel puede traer "César" o "Cesar" según cómo
    lo haya tipeado cada usuario, y ambas formas deben matchear igual.
    """
    propietario = _strip_accents(_safe_str(row.get("propietario", "")).strip().lower())
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
    """Devuelve True si el lead pertenece a Pauta (marketing).

    Regla de negocio (2026-07-03e): Pauta ahora incluye TikTok, Orgánico,
    Llamada telefónica, cualquier canal de redes sociales (Facebook,
    Instagram, WhatsApp, Messenger, etc.) y cualquier "Referido" cuyo Canal
    offline mencione "redes" — aunque diga "referido". El check de "redes"
    se evalúa ANTES que el de "referido puro" a propósito: por eso
    "Referido cliente activo - Redes" es Pauta, no Referido. Solo el
    referido que NO menciona "redes" es Referido puro.
    """
    canal_off = _safe_str(row.get("Canal offline", "")).strip().lower()
    canal_on = _safe_str(row.get("canal online", "")).strip().lower()

    # "Redes" en el Canal offline (incluso si dice "referido") → SIEMPRE Pauta.
    # Se evalúa antes que cualquier otro check, incluido el de "referido puro".
    if PAUTA_REDES_TERM in canal_off:
        return True

    # TikTok y Orgánico ahora son Pauta.
    if is_tiktok(row) or is_organico(row):
        return True

    # Cualquier canal de redes sociales explícito (Facebook/Instagram/
    # WhatsApp/Messenger/etc.) → Pauta, por substring (no igualdad exacta).
    if any(term in canal_off for term in SOCIAL_CHANNEL_TERMS):
        return True

    # Cualquier variante de "llamada" (Llamada Entrante, Llamada Telefónica,
    # etc.) → Pauta, por substring (no solo la igualdad exacta ya cubierta
    # por MARKETING_OFFLINE_CHANNELS más abajo).
    if PAUTA_LLAMADA_TERM in canal_off:
        return True

    # Referido puro (sin "redes" en el nombre) → NO es Pauta.
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


# Columnas booleanas derivadas que `precompute_derived_columns` calcula UNA
# SOLA VEZ por archivo cargado (ver `src/ui/upload.py`), para que el resto
# del código las reutilice via `get_mask` en lugar de recorrer el DataFrame
# fila por fila cada vez que compute_all_metrics/breakdowns/secciones se
# vuelven a ejecutar en cada rerun de Streamlit.
DERIVED_MASK_COLUMNS: dict[str, "callable"] = {
    "_is_marketing": is_marketing,
    "_is_tiktok": is_tiktok,
    "_is_organico": is_organico,
    "_is_cesar_augusto": is_cesar_augusto,
    "_is_paid_network": _is_paid_network,
}


def precompute_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula una sola vez los predicados costosos (is_marketing, is_tiktok,
    is_organico, is_cesar_augusto, _is_paid_network, validez de cierre y
    asesor comercial) y los guarda como columnas booleanas nuevas.

    Se llama UNA VEZ al cargar el archivo (cacheado en `src/ui/upload.py`
    via `st.cache_data`), no en cada rerun. `compute_all_metrics` y los
    módulos de `analytics/*.py` leen estas columnas a través de `get_mask`
    en vez de recalcular cada predicado con `.apply(func, axis=1)` sobre
    todo el dataset cada vez que el usuario cambia el filtro de mes u otro
    widget dispara un rerun — ninguna regla de negocio cambia, solo se deja
    de repetir el mismo cálculo.
    """
    out = df.copy()
    if out.empty:
        for col in DERIVED_MASK_COLUMNS:
            out[col] = pd.Series(dtype=bool)
        out["_is_valid_closure_estado"] = pd.Series(dtype=bool)
        out["_is_asesor_comercial"] = pd.Series(dtype=bool)
        return out

    for col, func in DERIVED_MASK_COLUMNS.items():
        out[col] = out.apply(func, axis=1)
    out["_is_valid_closure_estado"] = valid_closure_estado_mask(out)
    if "propietario" in out.columns:
        out["_is_asesor_comercial"] = out["propietario"].apply(is_asesor_comercial)
    else:
        out["_is_asesor_comercial"] = False
    return out


def valid_closure_event_mask(df: pd.DataFrame, date_col: str, year: int, month: int) -> pd.Series:
    """Máscara booleana: True si `date_col` cae en (year, month) Y el cierre es válido
    (estado != "inactivo")."""
    if date_col not in df.columns or df.empty:
        return pd.Series(False, index=df.index)
    s = pd.to_datetime(df[date_col], errors="coerce")
    in_month = (s.dt.year == year) & (s.dt.month == month)
    valid = df["_is_valid_closure_estado"] if "_is_valid_closure_estado" in df.columns else valid_closure_estado_mask(df)
    return in_month & valid


def _sum_valid_closures(
    df_full: pd.DataFrame, year: int, month: int, mask: pd.Series | None = None
) -> int:
    """Suma cierres válidos (estado != "inactivo") del mes en las 4 columnas de
    fecha de cierre, opcionalmente restringidos a `mask` (máscara booleana ya
    calculada sobre `df_full`, p.ej. is_marketing/is_organico/is_tiktok o su
    complemento). Antes recibía un `predicate(row)` y lo evaluaba con
    `.apply(axis=1)` una vez por cada una de las 4 columnas de fecha —
    redundante, porque el predicado no depende de la columna. Pasar la
    máscara ya calculada evita recomputar el mismo predicado 4 veces."""
    total = 0
    for col in CLOSE_DATE_COLS:
        m = valid_closure_event_mask(df_full, col, year, month)
        if mask is not None:
            m = m & mask
        total += int(m.sum())
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
            leads_pauta=0, leads_organico=0, leads_tiktok=0, leads_organico_tiktok=0,
            asignados=0, asignados_pauta=0, asignados_organico=0, asignados_tiktok=0,
            calificados=0, no_calificados=0,
            total_cierres=0,
            eficiencia_real=0.0, eficiencia_bruta=0.0, eficiencia_global=0.0,
            total_cierres_estricto=0,
            total_cierres_general=0, cierres_marketing=0, cierres_referidos=0,
            cierres_organico=0, cierres_tiktok=0, cierres_no_pauta=0,
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

    mkt_mask = get_mask(df_period, "_is_marketing", is_marketing)
    tiktok_mask = get_mask(df_period, "_is_tiktok", is_tiktok)
    organico_mask = get_mask(df_period, "_is_organico", is_organico)
    cesar_mask = get_mask(df_period, "_is_cesar_augusto", is_cesar_augusto)

    # "Leads generales" de Orgánico/TikTok excluyen a César Augusto: sus leads
    # entran completos vía Suma 1 (ver abajo), sin dividirse entre las
    # tarjetas individuales de Orgánico/TikTok.
    organico_generales_mask = organico_mask & ~cesar_mask
    tiktok_generales_mask = tiktok_mask & ~cesar_mask

    leads_pauta = int(mkt_mask.sum())
    leads_organico = int(organico_generales_mask.sum())
    leads_tiktok = int(tiktok_generales_mask.sum())
    # Regla 2026-07-03h: Suma 1 = TODO lead cuyo propietario sea César Augusto,
    # sin importar canal/origen de contacto (ya no se filtra por
    # Messenger/Instagram). Suma 2 = TikTok/Orgánico de canal (no-César).
    # Sin doble conteo: is_tiktok tiene prioridad sobre is_organico (ver
    # is_organico), así que un lead con Canal offline=TikTok y Origen de la
    # pauta=Orgánico cae una sola vez en Suma 2b (TikTok).
    leads_organico_tiktok = leads_organico + leads_tiktok + int(cesar_mask.sum())

    # --- Asignados: solo Asesores Comerciales ---
    if "_is_asesor_comercial" in df_period.columns:
        asignado_mask = df_period["_is_asesor_comercial"]
    elif "propietario" in df_period.columns:
        asignado_mask = df_period["propietario"].apply(is_asesor_comercial)
    else:
        asignado_mask = pd.Series(False, index=df_period.index)
    df_asignados = df_period[asignado_mask]
    asignados = int(asignado_mask.sum())
    asignados_pauta = int((asignado_mask & mkt_mask).sum())
    asignados_organico = int((asignado_mask & organico_generales_mask).sum())
    asignados_tiktok = int((asignado_mask & tiktok_generales_mask).sum())

    # --- Embudo estricto: Calificados/No calificados sobre Asignados ---
    calificados = int(is_qualified_mask(df_asignados).sum()) if not df_asignados.empty else 0
    no_calificados = asignados - calificados

    # Calificados por canal (movido antes de "Eficiencias" porque los usan
    # los campos legados calificados_pauta/no_calificados_pauta más abajo).
    # NO están restringidos a Asignados (a diferencia de `calificados` de
    # arriba) — se mantiene el criterio legado ya usado por
    # creados_pauta/creados_referido más abajo.
    df_mkt = df_period[mkt_mask]
    df_ref = df_period[~mkt_mask]
    calificados_pauta = int(is_qualified_mask(df_mkt).sum())
    calificados_referido = int(is_qualified_mask(df_ref).sum())

    # --- Cierres válidos (estado != "inactivo"), sumando las 4 columnas (multi-cierre)
    # sobre el dataset completo ---
    # cierres_marketing (Pauta) ahora INCLUYE TikTok/Orgánico/redes-referidos
    # (regla 2026-07-03e, ver is_marketing). cierres_organico_valid y
    # cierres_tiktok_valid se siguen calculando como desgloses informativos
    # (subconjuntos de cierres_marketing), pero NO se vuelven a sumar en los
    # totales de abajo — sumarlos de nuevo contaría esos cierres dos veces.
    mkt_mask_full = get_mask(df_full, "_is_marketing", is_marketing)
    organico_mask_full = get_mask(df_full, "_is_organico", is_organico)
    tiktok_mask_full = get_mask(df_full, "_is_tiktok", is_tiktok)
    # Equivale a "not is_marketing(row)": is_marketing ya incluye TikTok/Orgánico,
    # así que Referido puro es exactamente el complemento de los 3.
    referido_mask_full = ~(mkt_mask_full | organico_mask_full | tiktok_mask_full)

    cierres_marketing = _sum_valid_closures(df_full, year, month, mkt_mask_full)
    cierres_organico_valid = _sum_valid_closures(df_full, year, month, organico_mask_full)
    cierres_tiktok_valid = _sum_valid_closures(df_full, year, month, tiktok_mask_full)
    cierres_referidos = _sum_valid_closures(df_full, year, month, referido_mask_full)
    # "No pauta" = Referidos puros únicamente (TikTok/Orgánico ya son Pauta).
    cierres_no_pauta = cierres_referidos

    # Pauta (ahora incluye TikTok/Orgánico) + Referido puro = partición
    # binaria completa de TODOS los cierres válidos, sin huecos ni doble conteo.
    total_cierres = cierres_marketing
    total_cierres_general = cierres_marketing + cierres_referidos

    # --- Eficiencias (fórmulas exactas, 2026-07-03i) ---
    # % Eficiencia Real (antes "% Eficiencia Pauta") = (Cierres de Pauta * 100)
    # / Calificados del MES (total, no solo calificados_pauta) — qué fracción
    # de todo el universo que sí calificó terminó siendo un cierre de Pauta.
    eficiencia_real = (cierres_marketing * 100 / calificados) if calificados else 0.0
    denom_bruta = asignados_pauta + leads_organico + leads_tiktok + calificados + no_calificados
    eficiencia_bruta = (total_cierres * 100 / denom_bruta) if denom_bruta else 0.0

    # % Eficiencia Global = (Cierres de Pauta * 100) / Leads CREADOS del mes
    # (denominador más amplio: todo lo que entró, calificado o no).
    eficiencia_global = (cierres_marketing * 100 / creados) if creados else 0.0

    # --- Campos legados (mantener para compatibilidad con secciones/tests que ya existen) ---
    # df_mkt/df_ref/calificados_pauta/calificados_referido ya se calcularon
    # más arriba.
    creados_pauta = len(df_mkt)
    creados_referido = len(df_ref)
    no_calificados_pauta = creados_pauta - calificados_pauta
    no_calificados_referido = creados_referido - calificados_referido

    cierres_1 = int(valid_closure_event_mask(df_full, "Fecha de cierre", year, month).sum())
    cierres_2 = int(valid_closure_event_mask(df_full, "Fecha de segundo cierre", year, month).sum())
    cierres_3 = int(valid_closure_event_mask(df_full, "Fecha de tercer cierre", year, month).sum())
    cierres_4 = int(valid_closure_event_mask(df_full, "Fecha de 4to cierre", year, month).sum())
    cierres_adicionales = cierres_2 + cierres_3 + cierres_4

    paid_mask_full = get_mask(df_full, "_is_paid_network", _is_paid_network)
    df_paid_full = df_full[paid_mask_full]
    cierres_por_pautas = sum(
        int(valid_closure_event_mask(df_paid_full, col, year, month).sum())
        for col in CLOSE_DATE_COLS
    )

    es_pauta = get_mask(df_period, "_is_paid_network", _is_paid_network)
    leads_redes = int(es_pauta.sum())
    cierres_redes = cierres_por_pautas

    pct_calificacion = (calificados / asignados) if asignados else 0.0
    eficiencia_total = (total_cierres_general / calificados) if calificados else 0.0
    eficiencia_comerciales = (cierres_redes / leads_redes) if leads_redes else 0.0

    if "Fecha de cierre" in df_full.columns and year > 0:
        mask_1ro = valid_closure_event_mask(df_full, "Fecha de cierre", year, month)
        leads_1ro = df_full[mask_1ro]
        if not leads_1ro.empty:
            is_mkt_1ro = mkt_mask_full.loc[leads_1ro.index]
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
        _is_mkt = mkt_mask_full.loc[_sub.index]
        cierres_adicionales_pauta += int(_is_mkt.sum())
        cierres_adicionales_referido += int((~_is_mkt).sum())

    eficiencia_referido = (cierres_referidos / calificados_referido) if calificados_referido else 0.0

    # Suma ESTRICTA para la tarjeta "Total Cierres": Pauta(M) + Referidos(R) +
    # Adicionales, calculada a partir de los mismos 3 números que se muestran
    # en las tarjetas individuales, para que por construcción NUNCA se
    # desincronice de lo que ve el usuario en pantalla.
    total_cierres_estricto = cierres_pauta_primer + cierres_referido_primer + cierres_adicionales

    return Metrics(
        creados=creados,
        leads_pauta=leads_pauta, leads_organico=leads_organico, leads_tiktok=leads_tiktok,
        leads_organico_tiktok=leads_organico_tiktok,
        asignados=asignados, asignados_pauta=asignados_pauta,
        asignados_organico=asignados_organico, asignados_tiktok=asignados_tiktok,
        calificados=calificados, no_calificados=no_calificados,
        total_cierres=total_cierres,
        eficiencia_real=eficiencia_real, eficiencia_bruta=eficiencia_bruta,
        eficiencia_global=eficiencia_global,
        total_cierres_estricto=total_cierres_estricto,
        total_cierres_general=total_cierres_general,
        cierres_marketing=cierres_marketing, cierres_referidos=cierres_referidos,
        cierres_organico=cierres_organico_valid, cierres_tiktok=cierres_tiktok_valid,
        cierres_no_pauta=cierres_no_pauta,
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
