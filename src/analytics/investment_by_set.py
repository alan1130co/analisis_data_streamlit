import pandas as pd
from src.analytics.metrics import is_marketing, _is_valid_closure_estado


def investment_by_set(
    df_meta_sets: pd.DataFrame,
    df_clientify: pd.DataFrame | None,
    year: int,
    month: int,
) -> pd.DataFrame:
    """Inversión por conjunto de anuncios del mes.

    SIEMPRE devuelve: Conjunto, Gasto USD, Resultados, Costo/contacto, Impresiones, Clics
    Si hay Clientify con cierres del mes: agrega "Cierres atribuidos" y "Costo/cierre"
    """
    if df_meta_sets is None or df_meta_sets.empty:
        return pd.DataFrame()

    if "Nombre del conjunto de anuncios" not in df_meta_sets.columns:
        return pd.DataFrame()

    if "Importe gastado (USD)" not in df_meta_sets.columns:
        return pd.DataFrame()

    # Filtrar por mes según "Inicio del informe"
    df = df_meta_sets.copy()
    if "Inicio del informe" in df.columns:
        s = pd.to_datetime(df["Inicio del informe"], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month)
        df = df[mask]
        if df.empty:
            return pd.DataFrame()

    # Agrupar por conjunto
    agg_dict = {"Importe gastado (USD)": "sum"}
    if "Resultados" in df.columns:
        agg_dict["Resultados"] = "sum"
    if "Impresiones" in df.columns:
        agg_dict["Impresiones"] = "sum"
    if "Clics en el enlace" in df.columns:
        agg_dict["Clics en el enlace"] = "sum"
    if "Alcance" in df.columns:
        agg_dict["Alcance"] = "sum"

    out = df.groupby("Nombre del conjunto de anuncios").agg(agg_dict).reset_index()

    rename_map = {
        "Nombre del conjunto de anuncios": "Conjunto",
        "Importe gastado (USD)": "Gasto USD",
        "Resultados": "Contactos",
        "Clics en el enlace": "Clics",
    }
    out = out.rename(columns=rename_map)

    out["Gasto USD"] = out["Gasto USD"].fillna(0).round(2)

    if "Contactos" in out.columns:
        out["Contactos"] = out["Contactos"].fillna(0).astype(int)
        out["Costo/contacto"] = out.apply(
            lambda r: round(r["Gasto USD"] / r["Contactos"], 2)
            if r["Contactos"] > 0 else 0.0,
            axis=1,
        )

    if "Impresiones" in out.columns:
        out["Impresiones"] = out["Impresiones"].fillna(0).astype(int)
    if "Clics" in out.columns:
        out["Clics"] = out["Clics"].fillna(0).astype(int)

    # === Atribución proporcional de cierres ===
    if "Contactos" in out.columns and df_clientify is not None and not df_clientify.empty:
        cierres_pauta_total = 0
        if "Fecha de cierre" in df_clientify.columns:
            s = pd.to_datetime(df_clientify["Fecha de cierre"], errors="coerce")
            active = df_clientify.apply(_is_valid_closure_estado, axis=1)
            mask = (s.dt.year == year) & (s.dt.month == month) & active
            sub = df_clientify[mask]
            if not sub.empty:
                cierres_pauta_total = int(sub.apply(is_marketing, axis=1).sum())

        total_contactos = out["Contactos"].sum()
        if total_contactos > 0 and cierres_pauta_total > 0:
            out["Cierres atribuidos"] = (
                out["Contactos"] / total_contactos * cierres_pauta_total
            ).round(1)
            out["Costo/cierre"] = out.apply(
                lambda r: round(r["Gasto USD"] / r["Cierres atribuidos"], 2)
                if r["Cierres atribuidos"] > 0 else 0.0,
                axis=1,
            )

    return out.sort_values("Gasto USD", ascending=False).reset_index(drop=True)
