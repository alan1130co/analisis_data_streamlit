import pandas as pd
from src.analytics.metrics import is_marketing, _safe_str, _is_active_estado

CATEGORY_COLUMN = "Tipo de proceso"
CATEGORY_LABEL = "Tipo de proceso"

_CLOSURE_COLS = [
    "Fecha de cierre", "Fecha de segundo cierre",
    "Fecha de tercer cierre", "Fecha de 4to cierre",
]


def closures_by_process_type(
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Todos",
) -> pd.DataFrame:
    """Distribución de cierres del mes por tipo de proceso, filtrada por equipo."""
    if df_full.empty or CATEGORY_COLUMN not in df_full.columns:
        return pd.DataFrame(columns=[CATEGORY_LABEL, "Total", "Porcentaje"])

    active = df_full.apply(_is_active_estado, axis=1)
    rows = []
    for col in _CLOSURE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active
        sub = df_full[mask]
        if sub.empty:
            continue
        for _, row in sub.iterrows():
            es_mkt = is_marketing(row)
            if team == "Marketing (pautas)" and not es_mkt:
                continue
            if team == "Referidos" and es_mkt:
                continue
            cat = _safe_str(row.get(CATEGORY_COLUMN, "")).strip()
            if not cat or cat.lower() in {"nan", "none"}:
                cat = "No registrado"
            rows.append({CATEGORY_LABEL: cat})

    if not rows:
        return pd.DataFrame(columns=[CATEGORY_LABEL, "Total", "Porcentaje"])

    out = pd.DataFrame(rows)[CATEGORY_LABEL].value_counts().reset_index()
    out.columns = [CATEGORY_LABEL, "Total"]
    total = int(out["Total"].sum())
    out["Porcentaje"] = (out["Total"] / total * 100).round(1)
    return out


def available_periods(df_full: pd.DataFrame) -> list[tuple[int, int]]:
    """Lista de (año, mes) con al menos un cierre, de más reciente a más antiguo."""
    periods: set[tuple[int, int]] = set()
    for col in _CLOSURE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce").dropna()
        for ts in s:
            periods.add((ts.year, ts.month))
    return sorted(periods, reverse=True)
