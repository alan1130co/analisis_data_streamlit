import pandas as pd
import re

from src.analytics.metrics import is_marketing, _safe_str, _is_active_estado


_EXCLUIDOS = {"nan", "none", "sin definir", "no aplica"}

# Etiquetas administrativas que no son videos reales
_ADMIN_LABELS = ("no aplica", "no ingreso por redes", "fue referido")


def _limpiar_corchetes(valor) -> str:
    """Limpia valores tipo "['Facebook']" -> "Facebook". Devuelve '' si vacio o excluido."""
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if not s or s.lower() in _EXCLUIDOS:
        return ""
    match = re.search(r"\[['\"]([^'\"]+)['\"]\]", s)
    if match:
        extracted = match.group(1).strip()
        return "" if extracted.lower() in _EXCLUIDOS else extracted
    return s


def _es_etiqueta_admin(publi: str) -> bool:
    """True si la publicacion es una etiqueta administrativa, no un video real."""
    low = publi.lower()
    return any(tag in low for tag in _ADMIN_LABELS)


def _mapear_canal_a_red(canal_offline: str, origen_pauta: str = "") -> str:
    """Mapea a red social/categoria para el donut.

    "Origen de la pauta" es la señal autoritativa para Facebook/Instagram:
    cierres de Click-to-Message llegan con Canal offline genérico
    (p.ej. "Clientify - Whatsapp" o vacío), así que si no se prioriza el
    Origen, esos cierres de Instagram no se pintan en el reporte.
    """
    origen = (origen_pauta or "").strip().lower()
    if "instagram" in origen:
        return "Instagram"
    if "facebook" in origen:
        return "Facebook"

    if not canal_offline:
        return ""
    c = canal_offline.strip().lower()
    if "facebook" in c:
        return "Facebook"
    if "instagram" in c:
        return "Instagram"
    if "whatsapp" in c or "wsp" in c:
        return "WhatsApp"
    if "messenger" in c:
        return "Messenger"
    if "tiktok" in c or "tik tok" in c or c.replace("\xe1", "a") in {"organico", "organico "}:
        return "TikTok"
    if "referido cliente activo - redes" in c:
        return "Referido de Redes"
    if "formulario web" in c:
        return "Web"
    if "llamada" in c:
        return "Llamada"
    return ""


def closures_by_publication(
    df_clientify: pd.DataFrame,
    year: int,
    month: int,
) -> pd.DataFrame:
    """Cierres del mes (solo Fecha de cierre, 1ra col) de canales digitales/redes.

    Filtra por is_marketing()==True. Etiquetas administrativas como
    'No aplica/Fue referido' se redirigen a 'Sin publicacion marcada'.
    Columnas: Publicacion, Cierres, Porcentaje
    """
    cols_publi = "Publicacion por la que se contacto el cliente"

    if df_clientify is None or df_clientify.empty or cols_publi not in df_clientify.columns:
        return pd.DataFrame(columns=["Publicacion", "Cierres", "Porcentaje"])

    rows = []
    col = "Fecha de cierre"
    if col not in df_clientify.columns:
        return pd.DataFrame(columns=["Publicacion", "Cierres", "Porcentaje"])

    s = pd.to_datetime(df_clientify[col], errors="coerce")
    active = df_clientify.apply(_is_active_estado, axis=1)
    mask = (s.dt.year == year) & (s.dt.month == month) & active
    sub = df_clientify[mask]

    for _, row in sub.iterrows():
        if not is_marketing(row):
            continue
        publi = _limpiar_corchetes(row.get(cols_publi))
        if not publi or _es_etiqueta_admin(publi):
            publi = "Sin publicacion marcada"
        rows.append({"Publicacion": publi})

    if not rows:
        return pd.DataFrame(columns=["Publicacion", "Cierres", "Porcentaje"])

    out = pd.DataFrame(rows)["Publicacion"].value_counts().reset_index()
    out.columns = ["Publicacion", "Cierres"]
    total = int(out["Cierres"].sum())
    out["Porcentaje"] = (out["Cierres"] / total * 100).round(1)

    # "Sin publicacion marcada" siempre al final
    if "Sin publicacion marcada" in out["Publicacion"].values:
        sin_marcar = out[out["Publicacion"] == "Sin publicacion marcada"]
        resto = out[out["Publicacion"] != "Sin publicacion marcada"]
        out = pd.concat([resto, sin_marcar], ignore_index=True)

    return out


def closures_by_origen_pauta(
    df_clientify: pd.DataFrame,
    year: int,
    month: int,
) -> pd.DataFrame:
    """Cierres del mes (solo Fecha de cierre, 1ra col) por red social.

    Deriva la red desde Canal offline via _mapear_canal_a_red().
    Solo cuenta cierres de pauta (is_marketing()==True).
    Columnas: Origen, Cierres, Porcentaje
    """
    if df_clientify is None or df_clientify.empty:
        return pd.DataFrame(columns=["Origen", "Cierres", "Porcentaje"])

    col = "Fecha de cierre"
    if col not in df_clientify.columns:
        return pd.DataFrame(columns=["Origen", "Cierres", "Porcentaje"])

    s = pd.to_datetime(df_clientify[col], errors="coerce")
    active = df_clientify.apply(_is_active_estado, axis=1)
    mask = (s.dt.year == year) & (s.dt.month == month) & active
    sub = df_clientify[mask]

    rows = []
    for _, row in sub.iterrows():
        if not is_marketing(row):
            continue
        canal = _safe_str(row.get("Canal offline", "")).strip()
        origen_pauta = _safe_str(row.get("Origen de la pauta", "")).strip()
        origen = _mapear_canal_a_red(canal, origen_pauta)
        if not origen:
            continue
        rows.append({"Origen": origen})

    if not rows:
        return pd.DataFrame(columns=["Origen", "Cierres", "Porcentaje"])

    out = pd.DataFrame(rows)["Origen"].value_counts().reset_index()
    out.columns = ["Origen", "Cierres"]
    total = int(out["Cierres"].sum())
    out["Porcentaje"] = (out["Cierres"] / total * 100).round(1)
    return out


def available_periods(df_clientify: pd.DataFrame) -> list[tuple[int, int]]:
    """Lista de (anio, mes) con al menos un cierre."""
    periods = set()
    for col in ["Fecha de cierre", "Fecha de segundo cierre",
                "Fecha de tercer cierre", "Fecha de 4to cierre"]:
        if col not in df_clientify.columns:
            continue
        s = pd.to_datetime(df_clientify[col], errors="coerce").dropna()
        for ts in s:
            periods.add((ts.year, ts.month))
    return sorted(periods, reverse=True)
