"""Tests para src/analytics/comparison.py."""
from datetime import date, datetime

import pandas as pd
import pytest

from src.analytics.comparison import monthly_comparison


@pytest.fixture
def df():
    return pd.DataFrame([
        {
            "creado": datetime(2026, 3, 1),
            "propietario": "sofia",
            "estado": "activo",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 3, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "ana",
            "estado": "en transito",
            "Motivo de no cierre": "no se logró contactar",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox",
            "Canal offline": None,
            "Origen de la pauta": None,
        },
        {
            "creado": datetime(2026, 4, 5),
            "propietario": "sofia",
            "estado": "activo",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 10),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
    ])


def test_monthly_comparison_columnas(df):
    result = monthly_comparison(df, date(2026, 4, 1))
    assert set(result.columns) == {"Indicador", "mes_anterior", "mes_actual"}


def test_monthly_comparison_cinco_indicadores(df):
    result = monthly_comparison(df, date(2026, 4, 1))
    assert len(result) == 5


def test_monthly_comparison_indicadores_esperados(df):
    result = monthly_comparison(df, date(2026, 4, 1))
    indicadores = set(result["Indicador"].values)
    assert "Asignados" in indicadores
    assert "Calificados" in indicadores
    assert "Cierres pauta" in indicadores
    assert "Cierres referidos" in indicadores
    assert "Cierres totales (1+2+3+4)" in indicadores
    assert "Cierres (base)" not in indicadores


def test_monthly_comparison_valores_mes_anterior(df):
    result = monthly_comparison(df, date(2026, 4, 1))
    row = result[result["Indicador"] == "Asignados"].iloc[0]
    # Marzo tiene 1 lead con propietario
    assert row["mes_anterior"] == 1


def test_monthly_comparison_valores_mes_actual(df):
    result = monthly_comparison(df, date(2026, 4, 1))
    row = result[result["Indicador"] == "Asignados"].iloc[0]
    # Abril tiene 2 leads con propietario
    assert row["mes_actual"] == 2


def test_monthly_comparison_sin_mes_anterior():
    df_only_april = pd.DataFrame([{
        "creado": datetime(2026, 4, 1),
        "propietario": "sofia",
        "Motivo de no cierre": None,
        "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT,
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
        "canal online": "inbox",
        "Canal offline": None,
        "Origen de la pauta": None,
    }])
    result = monthly_comparison(df_only_april, date(2026, 4, 1))
    assert result.empty


def test_monthly_comparison_separa_pauta_y_referidos():
    """1 cierre pauta y 1 cierre referido cerrando en el mes actual."""
    df = pd.DataFrame([
        # Lead de pauta (marketing) creado en marzo, cierra en abril
        {
            "creado": datetime(2026, 3, 1),
            "propietario": "sofia",
            "estado": "activo",
            "Motivo de no cierre": None,
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 10),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        # Lead referido (no marketing) creado en marzo, cierra en abril
        {
            "creado": datetime(2026, 3, 2),
            "propietario": "ana",
            "estado": "activo",
            "Motivo de no cierre": None,
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 15),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox-referral",
            "Canal offline": "referido - cliente",
            "Origen de la pauta": None,
        },
        # Lead de abril (para que df_curr no esté vacío)
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "carlos",
            "estado": "en transito",
            "Motivo de no cierre": None,
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox",
            "Canal offline": None,
            "Origen de la pauta": None,
        },
    ])
    result = monthly_comparison(df, date(2026, 4, 1))
    pauta = result[result["Indicador"] == "Cierres pauta"].iloc[0]
    referidos = result[result["Indicador"] == "Cierres referidos"].iloc[0]
    assert pauta["mes_actual"] == 1
    assert referidos["mes_actual"] == 1
