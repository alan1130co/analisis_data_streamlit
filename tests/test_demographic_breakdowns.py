import pandas as pd
from src.analytics.closures_by_country import closures_by_country
from src.analytics.closures_by_age import closures_by_age, _rango_edad


def test_closures_by_country_filtra_por_team():
    df = pd.DataFrame([
        {
            "creado": pd.Timestamp("2026-04-01"), "país": "USA",
            "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-05"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": pd.Timestamp("2026-04-02"), "país": "Mexico",
            "Canal offline": "Referido externo", "canal online": "inbox-referral",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-10"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        },
    ])
    result_mkt = closures_by_country(df, 2026, 4, team="Marketing (pautas)")
    assert len(result_mkt) == 1
    assert result_mkt.iloc[0]["país"] == "USA"

    result_ref = closures_by_country(df, 2026, 4, team="Referidos")
    assert len(result_ref) == 1
    assert result_ref.iloc[0]["país"] == "Mexico"

    result_all = closures_by_country(df, 2026, 4, team="Todos")
    assert int(result_all["Total"].sum()) == 2


def test_closures_by_country_pais_vacio_es_no_registrado():
    df = pd.DataFrame([
        {
            "creado": pd.Timestamp("2026-04-01"), "país": "",
            "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-05"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        },
    ])
    result = closures_by_country(df, 2026, 4, team="Todos")
    assert result.iloc[0]["país"] == "No registrado"


def test_rango_edad_clasificacion():
    assert _rango_edad(15) == "Menor de edad"
    assert _rango_edad(20) == "18-24 años"
    assert _rango_edad(30) == "25-34 años"
    assert _rango_edad(70) == "65+ años"
    assert _rango_edad(None) == "No registrado"


def test_closures_by_age_calcula_edad_correcta():
    df = pd.DataFrame([
        {
            "creado": pd.Timestamp("2026-04-01"),
            "cumpleaños": pd.Timestamp("1990-06-15"),
            "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-15"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        },
    ])
    result = closures_by_age(df, 2026, 4, team="Todos")
    assert len(result) == 1
    assert result.iloc[0]["Rango de edad"] == "35-44 años"
