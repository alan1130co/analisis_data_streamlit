"""Tests para src/analytics/daily_sales.py."""
from datetime import date, datetime

import pandas as pd
import pytest

from src.analytics.daily_sales import daily_sales_by_advisor, daily_sales_total


@pytest.fixture
def df():
    return pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "sofia",
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": datetime(2026, 4, 10),
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 4, 2),
            "propietario": "ana",
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 3, 1),
            "propietario": "sofia",
            "Fecha de cierre": datetime(2026, 3, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])


def test_daily_sales_total_columnas(df):
    result = daily_sales_total(df, 2026, 4)
    assert set(result.columns) == {"dia", "Cierres"}


def test_daily_sales_agrupa_por_dia(df):
    result = daily_sales_total(df, 2026, 4)
    # Día 5 de abril: sofia (1er cierre) + ana (1er cierre) = 2
    dia_5 = result[result["dia"] == date(2026, 4, 5)].iloc[0]
    assert dia_5["Cierres"] == 2


def test_daily_sales_segundo_cierre_cuenta(df):
    result = daily_sales_total(df, 2026, 4)
    # Día 10 de abril: sofia (2do cierre) = 1
    dia_10 = result[result["dia"] == date(2026, 4, 10)].iloc[0]
    assert dia_10["Cierres"] == 1


def test_daily_sales_cross_month_no_aparece(df):
    result = daily_sales_total(df, 2026, 4)
    march_dates = [d for d in result["dia"] if d.month == 3]
    assert len(march_dates) == 0


def test_daily_sales_mes_sin_cierres_vacio():
    df_empty = pd.DataFrame(columns=[
        "propietario", "Fecha de cierre", "Fecha de segundo cierre",
        "Fecha de tercer cierre", "Fecha de 4to cierre",
    ])
    result = daily_sales_total(df_empty, 2026, 4)
    assert result.empty


def test_daily_sales_by_advisor_columnas(df):
    result = daily_sales_by_advisor(df, 2026, 4)
    assert {"dia", "propietario", "Cierres"}.issubset(result.columns)


def test_daily_sales_by_advisor_atribuye_correctamente(df):
    result = daily_sales_by_advisor(df, 2026, 4)
    dia_5_sofia = result[(result["dia"] == date(2026, 4, 5)) & (result["propietario"] == "sofia")]
    assert len(dia_5_sofia) == 1
    assert dia_5_sofia.iloc[0]["Cierres"] == 1
