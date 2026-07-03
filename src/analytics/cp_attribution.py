import pandas as pd
from src.data_sources.meta_cp_loader import normalize_phone, normalize_email
from src.analytics.metrics import is_marketing, _is_valid_closure_estado


def _get_clientify_closed_leads(
    df_clientify: pd.DataFrame,
    year: int,
    month: int,
) -> pd.DataFrame:
    """Devuelve solo los leads que cerraron en el mes indicado (por 1ra Fecha de cierre)."""
    if df_clientify is None or df_clientify.empty:
        return pd.DataFrame()
    if "Fecha de cierre" not in df_clientify.columns:
        return pd.DataFrame()

    s = pd.to_datetime(df_clientify["Fecha de cierre"], errors="coerce")
    active = df_clientify.apply(_is_valid_closure_estado, axis=1)
    mask = (s.dt.year == year) & (s.dt.month == month) & active
    closed = df_clientify[mask].copy()
    if closed.empty:
        return pd.DataFrame()

    # Solo cierres de pauta (marketing)
    closed = closed[closed.apply(is_marketing, axis=1)].copy()

    # Normalizar teléfono y email para el cruce
    tel_cols = [c for c in closed.columns if "teléfono" in c.lower() or "telefono" in c.lower()]
    email_cols = [c for c in closed.columns if "correo" in c.lower() or "email" in c.lower()]

    if tel_cols:
        closed["_tel_norm"] = closed[tel_cols[0]].apply(normalize_phone)
    else:
        closed["_tel_norm"] = ""

    if email_cols:
        closed["_email_norm"] = closed[email_cols[0]].apply(normalize_email)
    else:
        closed["_email_norm"] = ""

    return closed.reset_index(drop=True)


def match_cp_with_closures(
    df_cp: pd.DataFrame,
    df_clientify: pd.DataFrame,
    year: int,
    month: int,
) -> pd.DataFrame:
    """Cruza los CP de Meta con los cierres de Clientify.

    Devuelve un DataFrame con SOLO los CP que cerraron. Columnas:
    - Nombre CP (de Meta)
    - Nombre Clientify
    - Teléfono
    - Email
    - Video (ad_name)
    - Conjunto (adset_name)
    - Campaña (campaign_name)
    - Fecha CP (created_time)
    - Fecha cierre (Fecha de cierre)
    - Matcheo (por qué se hizo el match: "teléfono", "email", "ambos")
    """
    if df_cp is None or df_cp.empty:
        return pd.DataFrame()

    closed = _get_clientify_closed_leads(df_clientify, year, month)
    if closed.empty:
        return pd.DataFrame()

    matches = []
    for _, cp in df_cp.iterrows():
        tel_cp = cp.get("_tel_norm", "")
        email_cp = cp.get("_email_norm", "")

        # Buscar match en cierres
        match_tel = closed[closed["_tel_norm"] == tel_cp] if tel_cp else pd.DataFrame()
        match_email = closed[closed["_email_norm"] == email_cp] if email_cp else pd.DataFrame()

        matched_row = None
        matched_by = None

        if not match_tel.empty and not match_email.empty:
            # Si ambos matchean y son el mismo lead → "ambos"
            if match_tel.iloc[0].name == match_email.iloc[0].name:
                matched_row = match_tel.iloc[0]
                matched_by = "ambos"
            else:
                # Priorizar teléfono
                matched_row = match_tel.iloc[0]
                matched_by = "teléfono"
        elif not match_tel.empty:
            matched_row = match_tel.iloc[0]
            matched_by = "teléfono"
        elif not match_email.empty:
            matched_row = match_email.iloc[0]
            matched_by = "email"

        if matched_row is not None:
            matches.append({
                "Nombre CP (Meta)": cp.get("¿cuál_es_tu_nombre_completo?", ""),
                "Nombre Clientify": matched_row.get("nombre", ""),
                "Teléfono": cp.get("¿cuál_es_tu_número_de_teléfono?", ""),
                "Email": cp.get("email", ""),
                "Video": cp.get("ad_name", ""),
                "Conjunto": cp.get("adset_name", ""),
                "Campaña": cp.get("campaign_name", ""),
                "Fecha CP": cp.get("created_time", ""),
                "Fecha cierre": matched_row.get("Fecha de cierre", ""),
                "Matcheo": matched_by,
            })

    if not matches:
        return pd.DataFrame()
    return pd.DataFrame(matches)


def summary_by_video(df_cp: pd.DataFrame, df_matches: pd.DataFrame) -> pd.DataFrame:
    """Resumen agregado por video: CP generados, cerraron, tasa de conversión."""
    if df_cp is None or df_cp.empty:
        return pd.DataFrame()

    total_cp = df_cp.groupby("ad_name").size().reset_index(name="CP generados")
    total_cp = total_cp.rename(columns={"ad_name": "Video"})

    if df_matches is not None and not df_matches.empty:
        cerraron = df_matches.groupby("Video").size().reset_index(name="Cerraron")
        summary = total_cp.merge(cerraron, on="Video", how="left")
    else:
        summary = total_cp.copy()
        summary["Cerraron"] = 0

    summary["Cerraron"] = summary["Cerraron"].fillna(0).astype(int)
    summary["Tasa conversión %"] = (summary["Cerraron"] / summary["CP generados"] * 100).round(1)

    return summary.sort_values("Cerraron", ascending=False).reset_index(drop=True)
