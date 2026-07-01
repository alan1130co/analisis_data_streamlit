import pandas as pd
from src.analytics.closures_by_video import closures_by_video


def test_closures_by_video_atribuye_proporcionalmente():
    df_clientify = pd.DataFrame([
        {
            "creado": pd.Timestamp("2026-04-01"),
            "Canal offline": "Clientify - Whatsapp",
            "canal online": "paid social",
            "Motivo de no cierre": "",
            "Cantidad de cierres": 1,
            "Fecha de cierre": pd.Timestamp("2026-04-05"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "propietario": "Ana",
        },
        {
            "creado": pd.Timestamp("2026-04-02"),
            "Canal offline": "Clientify - Whatsapp",
            "canal online": "paid social",
            "Motivo de no cierre": "",
            "Cantidad de cierres": 1,
            "Fecha de cierre": pd.Timestamp("2026-04-10"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "propietario": "Juan",
        },
    ])
    df_meta = pd.DataFrame([
        {
            "Inicio del informe": pd.Timestamp("2026-04-01"),
            "Nombre del anuncio": "Video A",
            "Importe gastado (USD)": 600,
            "Nuevos contactos de mensajes": 8,
        },
        {
            "Inicio del informe": pd.Timestamp("2026-04-15"),
            "Nombre del anuncio": "Video B",
            "Importe gastado (USD)": 400,
            "Nuevos contactos de mensajes": 2,
        },
    ])
    result = closures_by_video(df_clientify, df_meta, 2026, 4)
    assert len(result) == 2
    # Video A tiene 8/10 = 80% → 2 * 0.8 = 1.6 cierres atribuidos
    assert result.iloc[0]["Video"] == "Video A"
    assert result.iloc[0]["Cierres atribuidos"] == 1.6
    assert result.iloc[1]["Cierres atribuidos"] == 0.4


def test_closures_by_video_sin_meta_devuelve_vacio():
    df_clientify = pd.DataFrame()
    result = closures_by_video(df_clientify, None, 2026, 4)
    assert result.empty


def test_closures_by_video_sin_cierres_no_crashea():
    df_clientify = pd.DataFrame()
    df_meta = pd.DataFrame([
        {
            "Inicio del informe": pd.Timestamp("2026-04-01"),
            "Nombre del anuncio": "Video A",
            "Importe gastado (USD)": 500,
            "Nuevos contactos de mensajes": 10,
        },
    ])
    result = closures_by_video(df_clientify, df_meta, 2026, 4)
    assert len(result) == 1
    assert result.iloc[0]["Cierres atribuidos"] == 0.0
