"""Tests para src/analytics/social_yearly.py."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.social_yearly import social_yearly


@pytest.fixture
def df():
    return pd.DataFrame([
        {
            "creado": datetime(2026, 1, 5),
            "propietario": "sofia",
            "estado": "activo",
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 1, 10),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 1, 10),
            "propietario": "ana",
            "estado": "en transito",
            "canal online": "inbox-referral",
            "Canal offline": "referido - amigo",
            "Origen de la pauta": None,
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 2, 1),
            "propietario": "sofia",
            "estado": "en transito",
            "canal online": "paid social",
            "Canal offline": "clientify - instagram",
            "Origen de la pauta": "instagram",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])


def test_social_yearly_tiene_12_meses(df):
    result = social_yearly(df, 2026)
    assert len(result) == 12


def test_social_yearly_columnas(df):
    result = social_yearly(df, 2026)
    assert set(result.columns) == {"mes", "Leads_redes", "Cierres_redes"}


def test_social_yearly_solo_marketing_en_leads(df):
    result = social_yearly(df, 2026)
    enero = result[result["mes"] == "2026-01"].iloc[0]
    # Lead sofia (marketing) + lead ana (referidos) → solo 1 de redes
    assert enero["Leads_redes"] == 1


def test_social_yearly_cuenta_cierres_en_mes(df):
    result = social_yearly(df, 2026)
    enero = result[result["mes"] == "2026-01"].iloc[0]
    # Sofia tiene Fecha de cierre en enero
    assert enero["Cierres_redes"] == 1


def test_social_yearly_febrero_sin_cierres(df):
    result = social_yearly(df, 2026)
    feb = result[result["mes"] == "2026-02"].iloc[0]
    assert feb["Leads_redes"] == 1
    assert feb["Cierres_redes"] == 0


def test_social_yearly_meses_sin_datos_son_cero(df):
    result = social_yearly(df, 2026)
    marzo = result[result["mes"] == "2026-03"].iloc[0]
    assert marzo["Leads_redes"] == 0
    assert marzo["Cierres_redes"] == 0
