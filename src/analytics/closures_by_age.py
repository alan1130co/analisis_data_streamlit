import pandas as pd
from src.analytics.metrics import is_marketing, _is_active_estado

_CLOSURE_COLS = [
    "Fecha de cierre", "Fecha de segundo cierre",
    "Fecha de tercer cierre", "Fecha de 4to cierre",
]

_AGE_ORDER = [
    "Menor de edad", "18-24 años", "25-34 años", "35-44 años",
    "45-54 años", "55-64 años", "65+ años", "No registrado",
]


def _rango_edad(edad) -> str:
    if edad is None or pd.isna(edad):
        return "No registrado"
    if edad < 18:
        return "Menor de edad"
    if edad <= 24:
        return "18-24 años"
    if edad <= 34:
        return "25-34 años"
    if edad <= 44:
        return "35-44 años"
    if edad <= 54:
        return "45-54 años"
    if edad <= 64:
        return "55-64 años"
    return "65+ años"


def closures_by_age(
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Todos",
) -> pd.DataFrame:
    """Distribución de cierres por rango de edad calculado desde 'cumpleaños'."""
    if df_full.empty:
        return pd.DataFrame(columns=["Rango de edad", "Total", "Porcentaje"])

    cumpleanos = (
        pd.to_datetime(df_full["cumpleaños"], errors="coerce", dayfirst=True)
        if "cumpleaños" in df_full.columns
        else pd.Series([pd.NaT] * len(df_full), index=df_full.index)
    )

    fecha_ref = pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)
    active = df_full.apply(_is_active_estado, axis=1)

    rows = []
    for col in _CLOSURE_COLS:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active
        sub_idx = df_full.index[mask]
        if len(sub_idx) == 0:
            continue
        for idx in sub_idx:
            row = df_full.loc[idx]
            es_mkt = is_marketing(row)
            if team == "Marketing (pautas)" and not es_mkt:
                continue
            if team == "Referidos" and es_mkt:
                continue
            cump = cumpleanos.loc[idx]
            edad = (fecha_ref - cump).days // 365 if pd.notna(cump) else None
            rows.append({"Rango de edad": _rango_edad(edad)})

    if not rows:
        return pd.DataFrame(columns=["Rango de edad", "Total", "Porcentaje"])

    out = pd.DataFrame(rows)["Rango de edad"].value_counts().reset_index()
    out.columns = ["Rango de edad", "Total"]
    total = int(out["Total"].sum())
    out["Porcentaje"] = (out["Total"] / total * 100).round(1)
    out["__sort"] = out["Rango de edad"].apply(
        lambda x: _AGE_ORDER.index(x) if x in _AGE_ORDER else 99
    )
    out = out.sort_values("__sort").drop(columns="__sort").reset_index(drop=True)
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
