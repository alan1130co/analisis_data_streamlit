"""Tests para src/analytics/trend.py."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.trend import monthly_trend
from src.config.settings import FOUNDING_DATE


@pytest.fixture
def df():
    return pd.DataFrame([
        {
            "creado": datetime(2026, 1, 5),
            "propietario": "sofia",
            "estado": "activo",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 1, 10),
        },
        {
            "creado": datetime(2026, 2, 1),
            "propietario": "ana",
            "estado": "en transito",
            "Motivo de no cierre": "no se logró contactar",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 3, 1),
            "propietario": "sofia",
            "estado": "activo",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 3, 5),
        },
    ])


def _months_from_founding(end_year: int, end_month: int) -> int:
    """Cuenta meses desde FOUNDING_DATE hasta (end_year, end_month) inclusive."""
    fy, fm = FOUNDING_DATE
    count = 0
    y, m = fy, fm
    while (y < end_year) or (y == end_year and m <= end_month):
        count += 1
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return count


def test_trend_rango_desde_founding(df):
    result = monthly_trend(df, 2026, 3)
    expected = _months_from_founding(2026, 3)
    assert len(result) == expected
    assert result.iloc[0]["mes"] == f"{FOUNDING_DATE[0]}-{FOUNDING_DATE[1]:02d}"
    assert result.iloc[-1]["mes"] == "2026-03"


def test_trend_columnas(df):
    result = monthly_trend(df, 2026, 3)
    assert set(result.columns) == {"mes", "Asignados", "Calificados", "Cierres"}


def test_trend_agrupa_enero(df):
    result = monthly_trend(df, 2026, 3)
    enero = result[result["mes"] == "2026-01"].iloc[0]
    assert enero["Asignados"] == 1
    assert enero["Cierres"] == 1
    assert enero["Calificados"] == 1


def test_trend_meses_sin_datos_dan_cero(df):
    result = monthly_trend(df, 2026, 4)
    april = result[result["mes"] == "2026-04"].iloc[0]
    assert april["Asignados"] == 0
    assert april["Cierres"] == 0


def test_trend_rango_multi_anio():
    df = pd.DataFrame([{
        "creado": datetime(2025, 12, 1),
        "propietario": "sofia",
        "Motivo de no cierre": None,
        "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT,
    }])
    result = monthly_trend(df, 2026, 1)
    meses = list(result["mes"])
    assert "2025-12" in meses
    assert "2026-01" in meses
    assert len(result) > 2


@pytest.mark.parametrize("mes", [(2024, 6), (2025, 3), (2026, 4), (2026, 7), (2026, 8)])
def test_trend_calificados_regla_estricta_uniforme_en_todos_los_meses(mes):
    """La regla estricta de Calificados (2026-08-12c) no depende del mes:
    un lead con motivo vacío y sin cierre NO debe calificar en NINGÚN mes
    del histórico — ni en meses viejos ni en agosto. `monthly_trend` no
    recibe ni aplica ningún filtro condicional por fecha además de agrupar
    por mes de 'creado'."""
    year, month = mes
    df = pd.DataFrame([{
        "creado": datetime(year, month, 15),
        "propietario": "sofia",
        "Motivo de no cierre": None,
        "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT,
    }])
    result = monthly_trend(df, end_year=year, end_month=month)
    row = result[result["mes"] == f"{year}-{month:02d}"].iloc[0]
    assert row["Calificados"] == 0, f"Falló para mes={year}-{month:02d}"
    assert row["Asignados"] == 1, f"Falló para mes={year}-{month:02d}"


def test_trend_cierres_es_suma_de_4_columnas_y_no_filtra_team():
    """La línea Cierres debe contar TODOS los cierres del mes (pauta + referidos)."""
    df = pd.DataFrame([
        # 1 cierre pauta en abril
        {
            "creado": pd.Timestamp("2026-04-01"),
            "Canal offline": "Clientify - Whatsapp",
            "canal online": "paid social",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-05"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "propietario": "Ana",
            "Motivo de no cierre": "",
        },
        # 1 cierre referido en abril
        {
            "creado": pd.Timestamp("2026-04-02"),
            "Canal offline": "Referido externo",
            "canal online": "inbox-referral",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-04-10"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "propietario": "Juan",
            "Motivo de no cierre": "",
        },
        # 1 segundo cierre referido en abril (creado en marzo)
        {
            "creado": pd.Timestamp("2026-03-01"),
            "Canal offline": "Referido externo",
            "canal online": "inbox-referral",
            "estado": "activo",
            "Fecha de cierre": pd.Timestamp("2026-03-15"),
            "Fecha de segundo cierre": pd.Timestamp("2026-04-20"),
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "propietario": "Juan",
            "Motivo de no cierre": "",
        },
    ])
    result = monthly_trend(df, end_year=2026, end_month=4)
    abril_row = result[result["mes"] == "2026-04"].iloc[0]
    assert abril_row["Cierres"] == 3, (
        f"Cierres en abril esperado=3, obtenido={abril_row['Cierres']}"
    )