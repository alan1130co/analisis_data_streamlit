from dataclasses import dataclass
import pandas as pd
from src.analytics.metrics import is_marketing, _is_valid_closure_estado


@dataclass
class MarketingInvestmentMetrics:
    """Métricas de inversión en pauta para un mes específico."""
    gasto_total: float
    impresiones: int
    alcance: int
    clics: int
    nuevos_contactos: int
    cpm_promedio: float
    leads_pauta: int
    cierres_pauta: int
    costo_por_lead: float
    costo_por_cierre: float
    costo_por_contacto_meta: float
    tasa_conversion_clic: float


def filter_meta_by_month(df_meta: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Filtra el CSV de Meta a las filas del mes (por 'Inicio del informe')."""
    if df_meta is None or df_meta.empty or "Inicio del informe" not in df_meta.columns:
        return pd.DataFrame()
    s = pd.to_datetime(df_meta["Inicio del informe"], errors="coerce")
    mask = (s.dt.year == year) & (s.dt.month == month)
    return df_meta[mask]


def compute_investment_metrics(
    df_clientify: pd.DataFrame,
    df_meta: pd.DataFrame,
    year: int,
    month: int,
) -> MarketingInvestmentMetrics:
    """Cruza Clientify (leads/cierres) con Meta (gasto) y devuelve métricas del mes."""

    # === Meta Ads del mes ===
    meta_mes = filter_meta_by_month(df_meta, year, month)

    if meta_mes.empty:
        gasto = 0.0
        impr = alcance = clics = contactos = 0
        cpm_prom = 0.0
    else:
        if "Importe gastado (USD)" in meta_mes.columns:
            gasto = float(meta_mes["Importe gastado (USD)"].sum() or 0)
        else:
            gasto = 0.0

        if "Impresiones" in meta_mes.columns:
            impr = int(meta_mes["Impresiones"].sum() or 0)
        else:
            impr = 0

        if "Alcance" in meta_mes.columns:
            alcance = int(meta_mes["Alcance"].sum() or 0)
        else:
            alcance = 0

        if "Clics en el enlace" in meta_mes.columns:
            clics = int(meta_mes["Clics en el enlace"].sum() or 0)
        else:
            clics = 0

        if "Nuevos contactos de mensajes" in meta_mes.columns:
            contactos = int(meta_mes["Nuevos contactos de mensajes"].fillna(0).sum())
        elif "Resultados" in meta_mes.columns:
            contactos = int(meta_mes["Resultados"].fillna(0).sum())
        else:
            contactos = 0

        cpm_prom = (gasto / impr * 1000) if impr else 0.0

    # === Clientify del mes ===
    if df_clientify is None or df_clientify.empty:
        leads_pauta = 0
        cierres_pauta = 0
    else:
        creado = pd.to_datetime(df_clientify["creado"], errors="coerce")
        mask_creado = (creado.dt.year == year) & (creado.dt.month == month)
        df_periodo = df_clientify[mask_creado]
        leads_pauta = 0 if df_periodo.empty else int(df_periodo.apply(is_marketing, axis=1).sum())

        cierres_pauta = 0
        active_full = df_clientify.apply(_is_valid_closure_estado, axis=1)
        for col in ["Fecha de cierre", "Fecha de segundo cierre",
                    "Fecha de tercer cierre", "Fecha de 4to cierre"]:
            if col not in df_clientify.columns:
                continue
            s = pd.to_datetime(df_clientify[col], errors="coerce")
            mask = (s.dt.year == year) & (s.dt.month == month) & active_full
            sub = df_clientify[mask]
            if sub.empty:
                continue
            cierres_pauta += int(sub.apply(is_marketing, axis=1).sum())

    costo_por_lead = (gasto / leads_pauta) if leads_pauta else 0.0
    costo_por_cierre = (gasto / cierres_pauta) if cierres_pauta else 0.0
    costo_por_contacto_meta = (gasto / contactos) if contactos else 0.0
    tasa_conversion_clic = (contactos / clics * 100) if clics else 0.0

    return MarketingInvestmentMetrics(
        gasto_total=round(gasto, 2),
        impresiones=impr,
        alcance=alcance,
        clics=clics,
        nuevos_contactos=contactos,
        cpm_promedio=round(cpm_prom, 2),
        leads_pauta=leads_pauta,
        cierres_pauta=cierres_pauta,
        costo_por_lead=round(costo_por_lead, 2),
        costo_por_cierre=round(costo_por_cierre, 2),
        costo_por_contacto_meta=round(costo_por_contacto_meta, 2),
        tasa_conversion_clic=round(tasa_conversion_clic, 1),
    )


def top_anuncios_del_mes(df_meta: pd.DataFrame, year: int, month: int, top_n: int = 5) -> pd.DataFrame:
    """Top N anuncios del mes por inversión."""
    meta_mes = filter_meta_by_month(df_meta, year, month)
    columnas_vacio = ["Anuncio", "Gasto USD", "Impresiones", "Clics", "Contactos", "Costo/Contacto"]
    if meta_mes.empty or "Nombre del anuncio" not in meta_mes.columns:
        return pd.DataFrame(columns=columnas_vacio)

    if "Importe gastado (USD)" not in meta_mes.columns:
        return pd.DataFrame(columns=columnas_vacio)

    agg_dict = {"Importe gastado (USD)": "sum"}
    if "Impresiones" in meta_mes.columns:
        agg_dict["Impresiones"] = "sum"
    if "Clics en el enlace" in meta_mes.columns:
        agg_dict["Clics en el enlace"] = "sum"
    if "Nuevos contactos de mensajes" in meta_mes.columns:
        agg_dict["Nuevos contactos de mensajes"] = "sum"

    df = meta_mes.groupby("Nombre del anuncio").agg(agg_dict).reset_index()

    rename_map = {
        "Nombre del anuncio": "Anuncio",
        "Importe gastado (USD)": "Gasto USD",
        "Clics en el enlace": "Clics",
        "Nuevos contactos de mensajes": "Contactos",
    }
    df = df.rename(columns=rename_map)

    if "Contactos" in df.columns:
        df["Contactos"] = df["Contactos"].fillna(0).astype(int)
        df["Costo/Contacto"] = df.apply(
            lambda r: round(r["Gasto USD"] / r["Contactos"], 2) if r["Contactos"] else 0.0,
            axis=1,
        )
    else:
        df["Contactos"] = 0
        df["Costo/Contacto"] = 0.0

    return df.sort_values("Gasto USD", ascending=False).head(top_n).reset_index(drop=True)
