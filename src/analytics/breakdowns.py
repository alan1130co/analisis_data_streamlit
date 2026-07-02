"""
Cálculos de desglose por asesor, canal y origen de leads.

Funciones puras: reciben DataFrame, devuelven DataFrame.
NO importan Streamlit ni nada de la UI.
"""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import is_marketing, is_qualified_mask, _safe_str, _is_active_estado
from src.config.settings import REFERIDO_PREFIX

_CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]


def _infer_period(df_period: pd.DataFrame) -> tuple[int, int]:
    """Infiere año y mes del período desde la columna 'creado' de df_period."""
    dates = pd.to_datetime(df_period["creado"], errors="coerce").dropna()
    if dates.empty:
        now = pd.Timestamp.now()
        return (int(now.year), int(now.month))
    first = dates.iloc[0]
    return (int(first.year), int(first.month))


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
    team: str = "Marketing (pautas)",
    only_with_closures: bool = True,
) -> pd.DataFrame:
    """Tabla de eficiencia por asesor, con columnas según el equipo seleccionado.

    team:
      - "Marketing (pautas)": columnas pauta + calificados + efic s/cal
      - "Referidos":          columnas referidos + calificados + efic s/cal
      - "Todos":              columnas pauta + referido + global + calificados totales
    """
    if df_period.empty or "propietario" not in df_period.columns:
        return pd.DataFrame()

    year, month = _infer_period(df_period)

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
            is_mkt = sub.apply(is_marketing, axis=1)
            sub = sub[is_mkt] if filter_marketing else sub[~is_mkt]
        for prop, cant in sub["propietario"].value_counts().items():
            result[prop] = result.get(prop, 0) + int(cant)
        return result

    is_mkt_period = df_period.apply(is_marketing, axis=1)
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


def pauta_vs_referidos(df_period: pd.DataFrame, df_full: pd.DataFrame) -> pd.DataFrame:
    """
    Cierres del mes divididos en Pauta (is_marketing) y Referidos.

    Cuenta cierres válidos (estado Activo) sumando las 4 fechas de cierre de
    df_full que caen en el mes. Columnas: Origen, Cantidad, Porcentaje.
    """
    empty = pd.DataFrame([
        {"Origen": "Pauta", "Cantidad": 0, "Porcentaje": 0.0},
        {"Origen": "Referidos", "Cantidad": 0, "Porcentaje": 0.0},
    ])
    if df_period.empty:
        return empty

    year, month = _infer_period(df_period)
    mkt_mask_full = df_full.apply(is_marketing, axis=1)
    active_full = df_full.apply(_is_active_estado, axis=1)

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


def cierres_por_canal(
    df_period: pd.DataFrame,
    df_full: pd.DataFrame,
    team: str = "Marketing (pautas)",
    only_marketing: bool | None = None,
) -> pd.DataFrame:
    """Cuenta TODOS los cierres del mes (las 4 columnas de fecha) atribuidos al canal del lead.

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

    year, month = _infer_period(df_period)
    active_full = df_full.apply(_is_active_estado, axis=1)

    rows = []
    for col in _CLOSE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active_full
        sub = df_full[mask]
        for _, row in sub.iterrows():
            canal = _safe_str(row.get("Canal offline", "")).strip()
            if not canal or canal.lower() in {"nan", "none"}:
                canal = "Sin canal (referido)"

            es_marketing = is_marketing(row)
            if team == "Marketing (pautas)" and not es_marketing:
                continue
            if team == "Referidos" and es_marketing:
                continue

            rows.append({"Canal": canal})

    if not rows:
        return empty

    out = pd.DataFrame(rows)["Canal"].value_counts().reset_index()
    out.columns = ["Canal", "Cantidad"]
    total = int(out["Cantidad"].sum())
    out["Porcentaje"] = (out["Cantidad"] / total * 100).round(1)
    out["Canal"] = out["Canal"].str.title()
    return out.reset_index(drop=True)
