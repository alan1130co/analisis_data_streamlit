import pandas as pd
from src.data_sources.meta_cp_loader import normalize_phone, normalize_email
from src.analytics.cp_attribution import match_cp_with_closures, summary_by_video


def test_normalize_phone_quita_espacios_y_signos():
    assert normalize_phone("405 400 3820") == "4054003820"
    assert normalize_phone("+1 9786017842") == "9786017842"  # quita +1
    assert normalize_phone("2394147867") == "2394147867"
    assert normalize_phone("(305) 555-1234") == "3055551234"
    assert normalize_phone(None) == ""
    assert normalize_phone("") == ""


def test_normalize_email():
    assert normalize_email("Juan@Gmail.COM") == "juan@gmail.com"
    assert normalize_email("  ana@test.com  ") == "ana@test.com"
    assert normalize_email(None) == ""


def test_match_cp_con_clientify():
    df_cp = pd.DataFrame([{
        "id": "1", "ad_name": "Video A", "adset_name": "CA_USA",
        "campaign_name": "Camp1", "created_time": "2026-06-01",
        "¿cuál_es_tu_nombre_completo?": "Juan Pérez",
        "¿cuál_es_tu_número_de_teléfono?": "+1 305 555 1234",
        "email": "juan@gmail.com",
        "_tel_norm": "3055551234", "_email_norm": "juan@gmail.com",
    }])
    df_clientify = pd.DataFrame([{
        "nombre": "Juan Pérez", "teléfono 1": "3055551234",
        "correo electrónico 1": "juan@gmail.com",
        "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
        "Fecha de cierre": pd.Timestamp("2026-06-15"),
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }])
    result = match_cp_with_closures(df_cp, df_clientify, 2026, 6)
    assert len(result) == 1
    assert result.iloc[0]["Video"] == "Video A"
    assert result.iloc[0]["Matcheo"] in {"teléfono", "email", "ambos"}


def test_summary_by_video():
    df_cp = pd.DataFrame([
        {"ad_name": "Video A"}, {"ad_name": "Video A"}, {"ad_name": "Video A"},
        {"ad_name": "Video B"}, {"ad_name": "Video B"},
    ])
    df_matches = pd.DataFrame([
        {"Video": "Video A"}, {"Video": "Video A"},
        {"Video": "Video B"},
    ])
    summary = summary_by_video(df_cp, df_matches)
    assert len(summary) == 2
    # Video A tiene más cierres, debe ir primero
    assert summary.iloc[0]["Video"] == "Video A"
    assert int(summary.iloc[0]["CP generados"]) == 3
    assert int(summary.iloc[0]["Cerraron"]) == 2


def test_match_sin_cp_vacio():
    result = match_cp_with_closures(pd.DataFrame(), pd.DataFrame(), 2026, 6)
    assert result.empty
