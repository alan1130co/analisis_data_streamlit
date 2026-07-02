import pandas as pd
from src.analytics.closures_by_gender import (
    closures_by_gender,
    _detectar_genero,
)


def test_detectar_genero_hombre():
    assert _detectar_genero("José Pérez") == "Hombre"
    assert _detectar_genero("Carlos") == "Hombre"
    assert _detectar_genero("juan rodriguez") == "Hombre"


def test_detectar_genero_mujer():
    assert _detectar_genero("María García") == "Mujer"
    assert _detectar_genero("Ana") == "Mujer"
    assert _detectar_genero("sofia de la hoz") == "Mujer"


def test_closures_by_gender_filtra_por_team():
    df = pd.DataFrame([
        {
            "creado": pd.Timestamp("2026-04-01"),
            "nombre": "María García",
            "Canal offline": "Clientify - Whatsapp",
            "canal online": "paid social",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-05"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": pd.Timestamp("2026-04-02"),
            "nombre": "Carlos Pérez",
            "Canal offline": "Referido externo",
            "canal online": "inbox-referral",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-10"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])
    result_mkt = closures_by_gender(df, 2026, 4, team="Marketing (pautas)")
    assert int(result_mkt[result_mkt["Género"] == "Mujer"]["Cantidad"].iloc[0]) == 1
    assert "Hombre" not in result_mkt["Género"].values

    result_all = closures_by_gender(df, 2026, 4, team="Todos")
    assert int(result_all["Cantidad"].sum()) == 2


def test_detectar_genero_nunca_devuelve_no_identificado():
    """Caso crítico: ningún cierre debe quedar como 'No identificado'."""
    nombres_test = [
        "Bryan", "Gloria", "Ingrith", "Jose", "Hayler", "Anyi", "Leonardo",
        "John", "Jonny", "Pedro", "Carlos", "Hector", "Norbey", "Obel",
        "Luis", "Andrés", "Yanira", "Daniela", "Gonzalo", "Olga",
        "Oscar", "Andres", "Paquita", "Udelfa", "Wendy", "Faiver", "Ana",
        "Yorlanis", "Yusneidi", "Edinwander", "Maibelys", "Geremin",
        "Anyelina", "X", "ZZZ", "",
    ]
    for n in nombres_test:
        result = _detectar_genero(n)
        assert result in {"Hombre", "Mujer"}, (
            f"'{n}' devolvió '{result}' — debería ser Hombre o Mujer"
        )


def test_detectar_genero_abril_2026_clasificacion_correcta():
    """Valida los 35 cierres reales de abril 2026."""
    casos = [
        ("Bryan Steven", "Hombre"), ("Gloria Cecilia", "Mujer"),
        ("Ingrith Paola", "Mujer"), ("Jose Luis", "Hombre"),
        ("Hayler Eliecer", "Hombre"), ("Anyi Lizeth", "Mujer"),
        ("Leonardo", "Hombre"), ("John Alexis", "Hombre"),
        ("Jonny Jose", "Hombre"), ("Pedro Leon", "Hombre"),
        ("Carlos Eduardo", "Hombre"), ("Hector Andres", "Hombre"),
        ("Norbey Alexander", "Hombre"), ("Obel Alfonso", "Hombre"),
        ("Luis David", "Hombre"), ("Andrés Felipe", "Hombre"),
        ("Yanira", "Mujer"), ("Daniela del Carmen", "Mujer"),
        ("Jose Angel", "Hombre"), ("Gonzalo", "Hombre"),
        ("Olga Susana", "Mujer"), ("Oscar Jojaxel", "Hombre"),
        ("Andres Mauricio", "Hombre"), ("Paquita Alexandra", "Mujer"),
        ("Udelfa", "Mujer"), ("Wendy Yohana", "Mujer"),
        ("Faiver", "Hombre"), ("Ana Maria", "Mujer"),
    ]
    for nombre, esperado in casos:
        result = _detectar_genero(nombre)
        assert result == esperado, (
            f"'{nombre}' dio '{result}', esperaba '{esperado}'"
        )
