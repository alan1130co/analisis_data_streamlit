import pandas as pd
from src.analytics.metrics import is_marketing


def closures_by_video(
    df_clientify: pd.DataFrame,
    df_meta: pd.DataFrame,
    year: int,
    month: int,
) -> pd.DataFrame:
    """Ranking de videos del mes con cierres atribuidos proporcionalmente a contactos.

    Columnas: Video, Gasto USD, Contactos, Cierres atribuidos, Costo/cierre
    """
    if df_meta is None or df_meta.empty or "Inicio del informe" not in df_meta.columns:
        return pd.DataFrame(columns=["Video", "Gasto USD", "Contactos", "Cierres atribuidos", "Costo/cierre"])

    s = pd.to_datetime(df_meta["Inicio del informe"], errors="coerce")
    mask = (s.dt.year == year) & (s.dt.month == month)
    meta_mes = df_meta[mask]
    if meta_mes.empty:
        return pd.DataFrame(columns=["Video", "Gasto USD", "Contactos", "Cierres atribuidos", "Costo/cierre"])

    # Cierres pauta del mes desde Clientify
    cierres_pauta_total = 0
    if df_clientify is not None and not df_clientify.empty:
        for col in ["Fecha de cierre", "Fecha de segundo cierre",
                    "Fecha de tercer cierre", "Fecha de 4to cierre"]:
            if col not in df_clientify.columns:
                continue
            s2 = pd.to_datetime(df_clientify[col], errors="coerce")
            m2 = (s2.dt.year == year) & (s2.dt.month == month)
            sub = df_clientify[m2]
            if sub.empty:
                continue
            cierres_pauta_total += int(sub.apply(is_marketing, axis=1).sum())

    agg = meta_mes.groupby("Nombre del anuncio").agg({
        "Importe gastado (USD)": "sum",
        "Nuevos contactos de mensajes": "sum",
    }).reset_index()
    agg.columns = ["Video", "Gasto USD", "Contactos"]
    agg["Contactos"] = agg["Contactos"].fillna(0).astype(int)
    agg["Gasto USD"] = agg["Gasto USD"].fillna(0).round(2)

    total_contactos = agg["Contactos"].sum()
    if total_contactos == 0 or cierres_pauta_total == 0:
        agg["Cierres atribuidos"] = 0.0
        agg["Costo/cierre"] = 0.0
    else:
        agg["Cierres atribuidos"] = (agg["Contactos"] / total_contactos * cierres_pauta_total).round(1)
        agg["Costo/cierre"] = agg.apply(
            lambda r: round(r["Gasto USD"] / r["Cierres atribuidos"], 2)
            if r["Cierres atribuidos"] > 0 else 0.0,
            axis=1,
        )

    return agg.sort_values("Cierres atribuidos", ascending=False).reset_index(drop=True)
