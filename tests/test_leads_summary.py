"""Tests para src/analytics/leads_summary.py."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.leads_summary import leads_summary


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
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        {
            "creado": datetime(2026, 2, 1),
            "propietario": "ana",
            "estado": "en transito",
            "Motivo de no cierre": "no se logró contactar",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "canal online": "inbox",
            "Canal offline": None,
            "Origen de la pauta": None,
        },
        {
            "creado": datetime(2026, 1, 15),
            "propietario": "carlos",
            "estado": "activo",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 1, 20),
            "canal online": "inbox-referral",
            "Canal offline": "referido - amigo",
            "Origen de la pauta": None,
        },
    ])


def test_leads_summary_columnas(df):
    result = leads_summary(df, 2026)
    assert set(result.columns) == {"mes", "Leads", "Calificados", "Cierres", "Referidos"}


def test_leads_summary_año_completo_12_filas(df):
    result = leads_summary(df, 2026)
    assert len(result) == 12


def test_leads_summary_enero_leads(df):
    result = leads_summary(df, 2026)
    enero = result[result["mes"] == "2026-01"].iloc[0]
    # sofia + carlos = 2 leads en enero
    assert enero["Leads"] == 2


def test_leads_summary_enero_redes(df):
    result = leads_summary(df, 2026)
    enero = result[result["mes"] == "2026-01"].iloc[0]
    # Solo sofia es marketing (paid social)
    assert enero["Referidos"] == 1


def test_leads_summary_enero_calificados(df):
    result = leads_summary(df, 2026)
    enero = result[result["mes"] == "2026-01"].iloc[0]
    # sofia: tiene cierre → calificada; carlos: "cliente potencial" → calificado
    assert enero["Calificados"] == 2


def test_leads_summary_mes_especifico(df):
    result = leads_summary(df, 2026, month=2)
    assert len(result) == 1
    assert result.iloc[0]["mes"] == "2026-02"
    assert result.iloc[0]["Leads"] == 1


def test_leads_summary_meses_sin_datos_son_cero(df):
    result = leads_summary(df, 2026)
    marzo = result[result["mes"] == "2026-03"].iloc[0]
    assert marzo["Leads"] == 0
    assert marzo["Calificados"] == 0


@pytest.mark.parametrize("year,month", [(2024, 6), (2025, 11), (2026, 1), (2026, 4), (2026, 8)])
def test_leads_summary_regla_calificados_uniforme_en_todos_los_meses(year, month):
    """La regla estricta de Calificados (2026-08-12c) es la misma para
    cualquier mes/año — un lead con motivo vacío y sin cierre NO debe
    calificar, sea en 2024, 2025 o agosto 2026. `leads_summary` no aplica
    ningún filtro condicional por fecha además de agrupar por mes."""
    df_mes = pd.DataFrame([{
        "creado": datetime(year, month, 10),
        "propietario": "sofia",
        "Motivo de no cierre": None,
        "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT,
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
    }])
    result = leads_summary(df_mes, year, month=month)
    row = result.iloc[0]
    assert row["Leads"] == 1, f"Falló para {year}-{month:02d}"
    assert row["Calificados"] == 0, f"Falló para {year}-{month:02d}"
