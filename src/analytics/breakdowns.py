"""
Cálculos de desglose por asesor, canal y origen de leads.

Funciones puras: reciben DataFrame, devuelven DataFrame.
NO importan Streamlit ni nada de la UI.
"""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import (
    is_marketing,
    is_qualified_mask,
    _safe_str,
    get_mask,
    valid_closure_estado_mask,
)
from src.config.settings import REFERIDO_PREFIX

_CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]

# Etiquetas de cohorte para pauta_vs_referidos_por_antiguedad — exportadas
# para que la UI (src/ui/sections/pauta_vs_referidos_antiguedad.py) y los
# tests no hardcodeen el string.
COHORTE_MISMO_MES = "Llegaron y cerraron este mes"
COHORTE_MES_ANTERIOR = "Llegaron antes y cerraron este mes"


def available_periods(df_full: pd.DataFrame) -> list[tuple[int, int]]:
    """Lista de (año, mes) con al menos un cierre (cualquiera de las 4
    fechas), de más reciente a más antiguo — mismo criterio y misma forma
    que el `available_periods` de cada módulo `analytics/closures_by_*.py`,
    para alimentar el selector de período de `pauta_vs_referidos` y
    `cierres_por_canal` (`src/ui/sections/`, ver `src/ui/period_selector.py`)."""
    periods: set[tuple[int, int]] = set()
    for col in _CLOSE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce").dropna()
        for ts in s:
            periods.add((ts.year, ts.month))
    return sorted(periods, reverse=True)


def _closures_in_month_mask(df: pd.DataFrame, year: int, month: int) -> pd.Series:
    """Máscara booleana: True si el lead tiene al menos un cierre en el mes dado."""
    mask = pd.Series(False, index=df.index)
    for col in _CLOSE_COLS:
        if col in df.columns:
            dt = pd.to_datetime(df[col], errors="coerce")
            mask |= (dt.dt.year == year) & (dt.dt.month == month)
    return mask


def efficiency_by_advisor(
    df_period: pd.DataFrame,
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Marketing (pautas)",
    only_with_closures: bool = True,
) -> pd.DataFrame:
    """Tabla de eficiencia por asesor, con columnas según el equipo seleccionado.

    `year`/`month` son OBLIGATORIOS: deben ser el período activo seleccionado
    en el frontend (el mismo usado para construir `df_period`). Antes se
    inferían leyendo la primera fecha de `df_period['creado']` con fallback
    silencioso a `pd.Timestamp.now()` si venía vacío — eso desincronizaba esta
    tabla del período elegido en el dropdown principal cuando el mes
    seleccionado no tenía leads CREADOS todavía (solo cierres de leads viejos).

    team:
      - "Marketing (pautas)": columnas pauta + calificados + efic s/cal
      - "Referidos":          columnas referidos + calificados + efic s/cal
      - "Todos":              columnas pauta + referido + global + calificados totales
    """
    if df_period.empty or "propietario" not in df_period.columns:
        return pd.DataFrame()

    def _cierres_por_asesor(filter_marketing: bool | None) -> dict[str, int]:
        """Cuenta cierres del mes por asesor — solo 1ra columna (Fecha de cierre)."""
        result: dict[str, int] = {}
        if "Fecha de cierre" not in df_full.columns:
            return result
        s = pd.to_datetime(df_full["Fecha de cierre"], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month)
        sub = df_full[mask]
        if sub.empty:
            return result
        if filter_marketing is not None:
            is_mkt = get_mask(sub, "_is_marketing", is_marketing)
            sub = sub[is_mkt] if filter_marketing else sub[~is_mkt]
        for prop, cant in sub["propietario"].value_counts().items():
            result[prop] = result.get(prop, 0) + int(cant)
        return result

    is_mkt_period = get_mask(df_period, "_is_marketing", is_marketing)
    df_pauta = df_period[is_mkt_period].copy()
    df_referido = df_period[~is_mkt_period].copy()

    leads_pauta_x_asesor = df_pauta.groupby("propietario").size().to_dict()
    leads_ref_x_asesor = df_referido.groupby("propietario").size().to_dict()

    if team == "Marketing (pautas)":
        df_pauta["_calif"] = is_qualified_mask(df_pauta)
        calif_x_asesor = df_pauta.groupby("propietario")["_calif"].sum().to_dict()
    elif team == "Referidos":
        df_referido["_calif"] = is_qualified_mask(df_referido)
        calif_x_asesor = df_referido.groupby("propietario")["_calif"].sum().to_dict()
    else:
        df_all = df_period.copy()
        df_all["_calif"] = is_qualified_mask(df_all)
        calif_x_asesor = df_all.groupby("propietario")["_calif"].sum().to_dict()

    cierres_pauta = _cierres_por_asesor(True)
    cierres_ref = _cierres_por_asesor(False)

    if team == "Marketing (pautas)":
        asesores = set(leads_pauta_x_asesor.keys()) | set(cierres_pauta.keys())
    elif team == "Referidos":
        asesores = set(leads_ref_x_asesor.keys()) | set(cierres_ref.keys())
    else:
        asesores = (
            set(cierres_pauta.keys()) | set(cierres_ref.keys())
            | set(calif_x_asesor.keys())
        )

    rows = []
    for asesor in asesores:
        if pd.isna(asesor) or str(asesor).strip().lower() in {"", "nan", "none"}:
            continue

        lp = int(leads_pauta_x_asesor.get(asesor, 0))
        lr = int(leads_ref_x_asesor.get(asesor, 0))
        cp = int(cierres_pauta.get(asesor, 0))
        cr = int(cierres_ref.get(asesor, 0))
        cal = int(calif_x_asesor.get(asesor, 0))

        nombre = asesor.title() if isinstance(asesor, str) else str(asesor)

        if team == "Marketing (pautas)":
            ep = round(cp / lp * 100, 1) if lp else 0.0
            efic_s_cal = round(cp / cal * 100, 1) if cal else 0.0
            rows.append({
                "Asesor": nombre,
                "Leads pauta": lp,
                "Cierres pauta": cp,
                "% Efic. pauta": ep,
                "Calificados": cal,
                "% Efic. s/Cal.": efic_s_cal,
            })
        elif team == "Referidos":
            er = round(cr / lr * 100, 1) if lr else 0.0
            efic_s_cal = round(cr / cal * 100, 1) if cal else 0.0
            rows.append({
                "Asesor": nombre,
                "Leads referidos": lr,
                "Cierres referidos": cr,
                "% Efic. referidos": er,
                "Calificados": cal,
                "% Efic. s/Cal.": efic_s_cal,
            })
        else:
            ep = round(cp / cal * 100, 1) if cal else 0.0
            eg = round((cp + cr) / cal * 100, 1) if cal else 0.0
            rows.append({
                "Asesor": nombre,
                "Calificados": cal,
                "Cierres pauta": cp,
                "Cierres referidos": cr,
                "% Efic. pauta": ep,
                "% Efic. global": eg,
            })

    df_out = pd.DataFrame(rows)
    if df_out.empty:
        return df_out

    if only_with_closures:
        if team == "Marketing (pautas)":
            df_out = df_out[df_out["Cierres pauta"] >= 1]
        elif team == "Referidos":
            df_out = df_out[df_out["Cierres referidos"] >= 1]
        else:
            df_out = df_out[(df_out["Cierres pauta"] + df_out["Cierres referidos"]) >= 1]

    sort_col = {
        "Marketing (pautas)": "% Efic. pauta",
        "Referidos": "% Efic. referidos",
    }.get(team, "% Efic. global")
    return df_out.sort_values(sort_col, ascending=False).reset_index(drop=True)


def pauta_vs_referidos(
    df_period: pd.DataFrame, df_full: pd.DataFrame, year: int, month: int
) -> pd.DataFrame:
    """
    Cierres del mes divididos en Pauta (is_marketing) y Referidos.

    `year`/`month` son OBLIGATORIOS: el período activo seleccionado en el
    frontend, no se infiere de los datos (ver nota en `efficiency_by_advisor`).

    Cuenta cierres válidos (estado Activo) sumando las 4 fechas de cierre de
    df_full que caen en el mes. Columnas: Origen, Cantidad, Porcentaje.
    """
    empty = pd.DataFrame([
        {"Origen": "Pauta", "Cantidad": 0, "Porcentaje": 0.0},
        {"Origen": "Referidos", "Cantidad": 0, "Porcentaje": 0.0},
    ])
    if df_period.empty:
        return empty

    mkt_mask_full = get_mask(df_full, "_is_marketing", is_marketing)
    active_full = valid_closure_estado_mask(df_full)

    pauta_n = 0
    ref_n = 0
    for col in _CLOSE_COLS:
        if col not in df_full.columns:
            continue
        dt = pd.to_datetime(df_full[col], errors="coerce")
        in_month = (dt.dt.year == year) & (dt.dt.month == month) & active_full
        pauta_n += int((in_month & mkt_mask_full).sum())
        ref_n += int((in_month & ~mkt_mask_full).sum())

    total = pauta_n + ref_n

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total else 0.0

    return pd.DataFrame([
        {"Origen": "Pauta",     "Cantidad": pauta_n, "Porcentaje": pct(pauta_n)},
        {"Origen": "Referidos", "Cantidad": ref_n,   "Porcentaje": pct(ref_n)},
    ])


def pauta_vs_referidos_por_antiguedad(
    df_period: pd.DataFrame, df_full: pd.DataFrame, year: int, month: int
) -> pd.DataFrame:
    """
    Mismo universo de cierres que `pauta_vs_referidos` (válidos del mes,
    clasificados Pauta/Referidos vía `is_marketing`), desglosado ADEMÁS por
    si el lead se creó ese mismo mes o antes (columna "creado").

    `year`/`month` son OBLIGATORIOS: el mismo período ya resuelto por el
    selector de la sección "Pauta vs Referidos" (no se infiere ni se pide un
    período propio — ver `render_pauta_vs_referidos_antiguedad`).

    El segundo balde (`COHORTE_MES_ANTERIOR`) es el COMPLEMENTO exacto del
    primero dentro de cada cierre válido del mes — no una condición
    independiente tipo "creado < inicio del mes" — para que `Cantidad.sum()`
    siempre dé el mismo total que `pauta_vs_referidos`, sin depender de que
    "creado" nunca venga nulo o posterior a la fecha de cierre (algo que no
    debería pasar en datos reales, pero así no hay riesgo de fuga).

    Columnas: Cohorte, Origen, Cantidad.
    """
    empty = pd.DataFrame([
        {"Cohorte": COHORTE_MISMO_MES, "Origen": "Pauta", "Cantidad": 0},
        {"Cohorte": COHORTE_MISMO_MES, "Origen": "Referidos", "Cantidad": 0},
        {"Cohorte": COHORTE_MES_ANTERIOR, "Origen": "Pauta", "Cantidad": 0},
        {"Cohorte": COHORTE_MES_ANTERIOR, "Origen": "Referidos", "Cantidad": 0},
    ])
    if df_period.empty or "creado" not in df_full.columns:
        return empty

    mkt_mask_full = get_mask(df_full, "_is_marketing", is_marketing)
    active_full = valid_closure_estado_mask(df_full)
    creado = pd.to_datetime(df_full["creado"], errors="coerce")
    same_month_mask = (creado.dt.year == year) & (creado.dt.month == month)

    counts = {
        (COHORTE_MISMO_MES, "Pauta"): 0,
        (COHORTE_MISMO_MES, "Referidos"): 0,
        (COHORTE_MES_ANTERIOR, "Pauta"): 0,
        (COHORTE_MES_ANTERIOR, "Referidos"): 0,
    }
    for col in _CLOSE_COLS:
        if col not in df_full.columns:
            continue
        dt = pd.to_datetime(df_full[col], errors="coerce")
        in_month = (dt.dt.year == year) & (dt.dt.month == month) & active_full
        mismo_mes = in_month & same_month_mask
        antes = in_month & ~same_month_mask
        counts[(COHORTE_MISMO_MES, "Pauta")] += int((mismo_mes & mkt_mask_full).sum())
        counts[(COHORTE_MISMO_MES, "Referidos")] += int((mismo_mes & ~mkt_mask_full).sum())
        counts[(COHORTE_MES_ANTERIOR, "Pauta")] += int((antes & mkt_mask_full).sum())
        counts[(COHORTE_MES_ANTERIOR, "Referidos")] += int((antes & ~mkt_mask_full).sum())

    return pd.DataFrame([
        {"Cohorte": cohorte, "Origen": origen, "Cantidad": cantidad}
        for (cohorte, origen), cantidad in counts.items()
    ])


_DETALLE_ANTIGUEDAD_COLUMNS = ["Cliente", "Fecha de creación", "Fecha de cierre", "Origen", "Cohorte"]


def pauta_vs_referidos_por_antiguedad_detalle(
    df_period: pd.DataFrame, df_full: pd.DataFrame, year: int, month: int
) -> pd.DataFrame:
    """
    Detalle fila-por-fila del mismo universo que agrega
    `pauta_vs_referidos_por_antiguedad`: un registro por cada CIERRE válido
    del mes (no por lead — un lead con 2 cierres en el mismo mes, p.ej. 1er y
    2do cierre, aporta 2 filas, igual que ya cuenta 2 en la versión agregada).

    `year`/`month` son OBLIGATORIOS: el mismo período ya resuelto por el
    selector de "Pauta vs Referidos" (ver docstring de la función hermana
    arriba — no se infiere ni se pide un período propio).

    "Cliente" viene de la columna "nombre" del Excel (la misma que usa
    `closures_by_gender.py`) si existe; si no, queda vacío — no rompe el
    resto de la tabla, mismo criterio defensivo que ya usa esa sección.

    Columnas: Cliente, Fecha de creación, Fecha de cierre, Origen, Cohorte.
    Ordenado por "Fecha de creación" ascendente (más antiguos primero).
    """
    empty = pd.DataFrame(columns=_DETALLE_ANTIGUEDAD_COLUMNS)
    if df_period.empty or "creado" not in df_full.columns:
        return empty

    mkt_mask_full = get_mask(df_full, "_is_marketing", is_marketing)
    active_full = valid_closure_estado_mask(df_full)
    creado = pd.to_datetime(df_full["creado"], errors="coerce")
    same_month_mask = (creado.dt.year == year) & (creado.dt.month == month)
    tiene_nombre = "nombre" in df_full.columns

    rows = []
    for col in _CLOSE_COLS:
        if col not in df_full.columns:
            continue
        dt = pd.to_datetime(df_full[col], errors="coerce")
        in_month = (dt.dt.year == year) & (dt.dt.month == month) & active_full
        sub = df_full[in_month]
        if sub.empty:
            continue
        for idx, row in sub.iterrows():
            rows.append({
                "Cliente": _safe_str(row.get("nombre", "")) if tiene_nombre else "",
                "Fecha de creación": creado.loc[idx],
                "Fecha de cierre": dt.loc[idx],
                "Origen": "Pauta" if mkt_mask_full.loc[idx] else "Referidos",
                "Cohorte": COHORTE_MISMO_MES if same_month_mask.loc[idx] else COHORTE_MES_ANTERIOR,
            })

    if not rows:
        return empty

    result = pd.DataFrame(rows, columns=_DETALLE_ANTIGUEDAD_COLUMNS)
    return result.sort_values("Fecha de creación", ascending=True).reset_index(drop=True)


_CANALES_WHATSAPP_FACEBOOK_CP = {
    "clientify - whatsapp": "Clientify - Whatsapp",
    "formulario de facebook - cliente potencial": "Formulario de Facebook - Cliente Potencial",
}


def cierres_whatsapp_facebook_cp_por_mes_origen(
    df_period: pd.DataFrame, df_full: pd.DataFrame, year: int, month: int
) -> pd.DataFrame:
    """Cierres válidos del mes (mismo criterio que `pauta_vs_referidos`:
    estado != "inactivo", suma de las 4 fechas de cierre) restringidos a
    leads cuyo "Canal offline" sea EXACTAMENTE "Clientify - Whatsapp" o
    "Formulario de Facebook - Cliente Potencial" (valores confirmados contra
    el Excel real 2026-09-04), agrupados por mes/año de creación del lead
    ("creado") — no la cohorte binaria mismo-mes/antes de
    `pauta_vs_referidos_por_antiguedad`, sino cada mes de origen individual.

    `year`/`month` son OBLIGATORIOS: el mismo período ya resuelto por el
    selector de la sección "Pauta vs Referidos" (mismo patrón que las
    funciones hermanas de arriba).

    Columnas: "Mes de Origen" (str, formato "YYYY-MM"), "Canal", "Cantidad".
    Formato largo, ordenado cronológicamente ascendente por Mes de Origen.
    Si una combinación (mes, canal) no tuvo cierres, simplemente no aparece
    en el resultado (la UI la rellena con 0 al armar las barras).
    """
    empty = pd.DataFrame(columns=["Mes de Origen", "Canal", "Cantidad"])
    if df_period.empty or "creado" not in df_full.columns or "Canal offline" not in df_full.columns:
        return empty

    active_full = valid_closure_estado_mask(df_full)
    canal_off = df_full["Canal offline"].apply(_safe_str).str.strip().str.lower()
    canal_mask = canal_off.isin(_CANALES_WHATSAPP_FACEBOOK_CP.keys())
    creado = pd.to_datetime(df_full["creado"], errors="coerce")
    mes_origen = creado.dt.strftime("%Y-%m")

    frames = []
    for col in _CLOSE_COLS:
        if col not in df_full.columns:
            continue
        dt = pd.to_datetime(df_full[col], errors="coerce")
        in_month = (dt.dt.year == year) & (dt.dt.month == month) & active_full & canal_mask
        if not in_month.any():
            continue
        frames.append(pd.DataFrame({
            "Mes de Origen": mes_origen[in_month],
            "Canal": canal_off[in_month].map(_CANALES_WHATSAPP_FACEBOOK_CP),
        }))

    if not frames:
        return empty

    all_rows = pd.concat(frames, ignore_index=True).dropna(subset=["Mes de Origen"])
    if all_rows.empty:
        return empty

    out = all_rows.groupby(["Mes de Origen", "Canal"]).size().reset_index(name="Cantidad")
    return out.sort_values("Mes de Origen", ascending=True).reset_index(drop=True)


def cierres_por_canal(
    df_period: pd.DataFrame,
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Marketing (pautas)",
    only_marketing: bool | None = None,
) -> pd.DataFrame:
    """Cuenta TODOS los cierres del mes (las 4 columnas de fecha) atribuidos al canal del lead.

    `year`/`month` son OBLIGATORIOS: el período activo seleccionado en el
    frontend, no se infiere de los datos (ver nota en `efficiency_by_advisor`).

    Filtra por team:
    - "Marketing (pautas)": solo cierres cuyo lead is_marketing=True
    - "Referidos": solo cierres cuyo lead is_marketing=False
    - "Todos": incluye todos

    Columnas: Canal, Cantidad, Porcentaje.
    """
    # Backwards compat: only_marketing kwarg maps to team
    if only_marketing is not None:
        team = "Marketing (pautas)" if only_marketing else "Todos"

    empty = pd.DataFrame(columns=["Canal", "Cantidad", "Porcentaje"])
    if df_period.empty:
        return empty

    active_full = valid_closure_estado_mask(df_full)
    mkt_mask_full = get_mask(df_full, "_is_marketing", is_marketing)

    canales = []
    for col in _CLOSE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active_full
        if team == "Marketing (pautas)":
            mask = mask & mkt_mask_full
        elif team == "Referidos":
            mask = mask & ~mkt_mask_full
        sub = df_full[mask]
        if sub.empty:
            continue
        canal = sub.get("Canal offline", pd.Series("", index=sub.index)).apply(_safe_str).str.strip()
        canal = canal.mask(canal.eq("") | canal.str.lower().isin({"nan", "none"}), "Sin canal (referido)")
        canales.append(canal)

    if not canales:
        return empty

    out = pd.concat(canales).value_counts().reset_index()
    out.columns = ["Canal", "Cantidad"]
    total = int(out["Cantidad"].sum())
    out["Porcentaje"] = (out["Cantidad"] / total * 100).round(1)
    out["Canal"] = out["Canal"].str.title()
    return out.reset_index(drop=True)
