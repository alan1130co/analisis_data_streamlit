import pandas as pd
from src.analytics.closures_by_publication import (
    closures_by_publication,
    closures_by_origen_pauta,
    _limpiar_corchetes,
    _mapear_canal_a_red,
)

_BASE_MKT = {
    "Canal offline": "clientify - whatsapp",
    "canal online": "paid social",
    "Fecha de segundo cierre": pd.NaT,
    "Fecha de tercer cierre": pd.NaT,
    "Fecha de 4to cierre": pd.NaT,
}
_BASE_REF = {
    "Canal offline": "referido externo",
    "canal online": "inbox",
    "Fecha de segundo cierre": pd.NaT,
    "Fecha de tercer cierre": pd.NaT,
    "Fecha de 4to cierre": pd.NaT,
}


# ---------------------------------------------------------------------------
# _limpiar_corchetes
# ---------------------------------------------------------------------------

def test_limpiar_corchetes():
    assert _limpiar_corchetes("['Facebook']") == "Facebook"
    assert _limpiar_corchetes("['Sin definir']") == ""
    assert _limpiar_corchetes("Facebook") == "Facebook"
    assert _limpiar_corchetes("No Aplica") == ""
    assert _limpiar_corchetes(None) == ""
    assert _limpiar_corchetes("nan") == ""
    assert _limpiar_corchetes("") == ""


# ---------------------------------------------------------------------------
# _mapear_canal_a_red
# ---------------------------------------------------------------------------

def test_mapear_canal_a_red():
    assert _mapear_canal_a_red("Clientify - Facebook") == "Facebook"
    assert _mapear_canal_a_red("Formulario de Facebook - Cliente Potencial") == "Facebook"
    assert _mapear_canal_a_red("Clientify - Instagram") == "Instagram"
    assert _mapear_canal_a_red("Clientify - Whatsapp") == "WhatsApp"
    assert _mapear_canal_a_red("Tiktok") == "TikTok"
    # Organico con y sin tilde -> TikTok
    assert _mapear_canal_a_red("Org\xe1nico") == "TikTok"
    assert _mapear_canal_a_red("organico") == "TikTok"
    assert _mapear_canal_a_red("Referido cliente activo - Redes") == "Referido de Redes"
    # Canales que no son de redes
    assert _mapear_canal_a_red("Referido externo") == ""
    assert _mapear_canal_a_red("") == ""


# ---------------------------------------------------------------------------
# closures_by_publication
# ---------------------------------------------------------------------------

def test_closures_by_publication_agrupa_correcto():
    """Leads de pauta (1ra col): los con publi se agrupan; sin publi -> 'Sin publicacion marcada'."""
    df = pd.DataFrame([
        {**_BASE_MKT, "Publicacion por la que se contacto el cliente": "Video 2",
         "Fecha de cierre": pd.Timestamp("2026-05-01")},
        {**_BASE_MKT, "Publicacion por la que se contacto el cliente": "Video 2",
         "Fecha de cierre": pd.Timestamp("2026-05-10")},
        {**_BASE_MKT, "Publicacion por la que se contacto el cliente": "Comentario corto",
         "Fecha de cierre": pd.Timestamp("2026-05-15")},
        # Sin publicacion -> "Sin publicacion marcada" (es marketing, no se descarta)
        {**_BASE_MKT, "Publicacion por la que se contacto el cliente": None,
         "Fecha de cierre": pd.Timestamp("2026-05-20")},
    ])
    result = closures_by_publication(df, 2026, 5)
    assert len(result) == 3
    assert result.iloc[0]["Publicacion"] == "Video 2"
    assert int(result.iloc[0]["Cierres"]) == 2
    assert result.iloc[-1]["Publicacion"] == "Sin publicacion marcada"


def test_closures_by_publication_excluye_referidos():
    """Cierres de referido NO se incluyen aunque tengan publicacion marcada."""
    df = pd.DataFrame([
        {**_BASE_MKT, "Publicacion por la que se contacto el cliente": "Video 1",
         "Fecha de cierre": pd.Timestamp("2026-05-01")},
        {**_BASE_REF, "Publicacion por la que se contacto el cliente": "Video 2",
         "Fecha de cierre": pd.Timestamp("2026-05-02")},
    ])
    result = closures_by_publication(df, 2026, 5)
    assert int(result["Cierres"].sum()) == 1
    assert result.iloc[0]["Publicacion"] == "Video 1"


def test_closures_by_publication_incluye_organico():
    """Canal Organico (is_marketing=True) se incluye; Referido externo, no."""
    df = pd.DataFrame([
        {"Canal offline": "organico", "canal online": "",
         "Publicacion por la que se contacto el cliente": "Video 1",
         "Fecha de cierre": pd.Timestamp("2026-05-01"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"Canal offline": "clientify - whatsapp", "canal online": "",
         "Publicacion por la que se contacto el cliente": None,
         "Fecha de cierre": pd.Timestamp("2026-05-05"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"Canal offline": "referido externo", "canal online": "",
         "Publicacion por la que se contacto el cliente": "Video 2",
         "Fecha de cierre": pd.Timestamp("2026-05-10"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = closures_by_publication(df, 2026, 5)
    assert int(result["Cierres"].sum()) == 2, f"Solo Organico+Whatsapp deben contarse, total={result['Cierres'].sum()}"
    if "Sin publicacion marcada" in result["Publicacion"].values:
        assert result.iloc[-1]["Publicacion"] == "Sin publicacion marcada"


def test_tabla_excluye_no_aplica():
    """Etiqueta 'No aplica/Fue referido...' se redirige a 'Sin publicacion marcada'."""
    df = pd.DataFrame([
        {**_BASE_MKT,
         "Publicacion por la que se contacto el cliente": "No aplica/Fue referido/No ingreso por redes",
         "Fecha de cierre": pd.Timestamp("2026-05-01")},
        {**_BASE_MKT,
         "Publicacion por la que se contacto el cliente": "USA - Tienes audiencia y aun sin abogado",
         "Fecha de cierre": pd.Timestamp("2026-05-05")},
    ])
    result = closures_by_publication(df, 2026, 5)
    publicaciones = result["Publicacion"].tolist()
    assert "No aplica/Fue referido/No ingreso por redes" not in publicaciones
    assert "Sin publicacion marcada" in publicaciones
    assert int(result["Cierres"].sum()) == 2


# ---------------------------------------------------------------------------
# closures_by_origen_pauta
# ---------------------------------------------------------------------------

def test_closures_by_origen_pauta_usa_canal_offline():
    """La funcion deriva el origen desde Canal offline, no Origen de la pauta."""
    df = pd.DataFrame([
        {"Canal offline": "clientify - whatsapp", "canal online": "paid social",
         "Fecha de cierre": pd.Timestamp("2026-05-01"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"Canal offline": "formulario de facebook - cliente potencial", "canal online": "",
         "Fecha de cierre": pd.Timestamp("2026-05-02"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido externo -> excluido por is_marketing=False
        {"Canal offline": "referido externo", "canal online": "",
         "Fecha de cierre": pd.Timestamp("2026-05-03"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = closures_by_origen_pauta(df, 2026, 5)
    assert int(result["Cierres"].sum()) == 2
    origenes = result["Origen"].tolist()
    assert "WhatsApp" in origenes
    assert "Facebook" in origenes


def test_donut_organico_va_a_tiktok():
    """Orgánico + Tiktok se unifican como 'TikTok' en el donut."""
    df = pd.DataFrame([
        {"Canal offline": "org\xe1nico", "canal online": "",
         "Fecha de cierre": pd.Timestamp("2026-05-01"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"Canal offline": "tiktok", "canal online": "",
         "Fecha de cierre": pd.Timestamp("2026-05-02"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = closures_by_origen_pauta(df, 2026, 5)
    assert len(result) == 1
    assert result.iloc[0]["Origen"] == "TikTok"
    assert int(result.iloc[0]["Cierres"]) == 2
