import pandas as pd
from src.analytics.investment_by_set import investment_by_set


def test_investment_by_set_calcula_costo_contacto():
    df_meta = pd.DataFrame([
        {"Inicio del informe": pd.Timestamp("2026-06-01"),
         "Nombre del conjunto de anuncios": "CA_USA",
         "Importe gastado (USD)": 1170.58,
         "Resultados": 225,
         "Impresiones": 55515,
         "Clics en el enlace": 1043},
        {"Inicio del informe": pd.Timestamp("2026-06-01"),
         "Nombre del conjunto de anuncios": "CA_CALIFORNIA",
         "Importe gastado (USD)": 607.72,
         "Resultados": 81,
         "Impresiones": 24890,
         "Clics en el enlace": 445},
    ])
    result = investment_by_set(df_meta, None, 2026, 6)
    assert len(result) == 2
    assert result.iloc[0]["Conjunto"] == "CA_USA"  # mayor gasto primero
    assert result.iloc[0]["Costo/contacto"] == round(1170.58 / 225, 2)


def test_investment_by_set_atribuye_cierres_proporcional():
    df_meta = pd.DataFrame([
        {"Inicio del informe": pd.Timestamp("2026-06-01"),
         "Nombre del conjunto de anuncios": "CA_USA",
         "Importe gastado (USD)": 600,
         "Resultados": 80},
        {"Inicio del informe": pd.Timestamp("2026-06-01"),
         "Nombre del conjunto de anuncios": "CA_CALIFORNIA",
         "Importe gastado (USD)": 400,
         "Resultados": 20},
    ])
    df_clientify = pd.DataFrame([
        {"Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
         "estado": "activo",
         "Fecha de cierre": pd.Timestamp("2026-06-05"),
         "Fecha de segundo cierre": pd.NaT,
         "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
         "estado": "activo",
         "Fecha de cierre": pd.Timestamp("2026-06-10"),
         "Fecha de segundo cierre": pd.NaT,
         "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = investment_by_set(df_meta, df_clientify, 2026, 6)
    # CA_USA tiene 80/100 = 80% → 2 cierres * 0.8 = 1.6
    assert result.iloc[0]["Cierres atribuidos"] == 1.6
    assert result.iloc[1]["Cierres atribuidos"] == 0.4


def test_investment_by_set_sin_datos_vacio():
    assert investment_by_set(None, None, 2026, 6).empty
    assert investment_by_set(pd.DataFrame(), None, 2026, 6).empty
