"""Tests para src/analytics/funnel.py."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.funnel import funnel_by_advisor


@pytest.fixture
def leads():
    return pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "sofia",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
        },
        {
            "creado": datetime(2026, 4, 2),
            "propietario": "ana",
            "Motivo de no cierre": "no se logró contactar",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox",
            "Canal offline": None,
        },
        {
            "creado": datetime(2026, 4, 3),
            "propietario": "sofia",
            "Motivo de no cierre": None,
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
        },
    ])


def test_funnel_ordenado_por_asignados(leads):
    result = funnel_by_advisor(leads, leads)
    # Solo Sofia aparece (tiene cierres); Ana queda excluida
    assert result.iloc[0]["Asesor"] == "Sofia"
    assert result.iloc[0]["Asignados"] == 2
    assert len(result) == 1


def test_funnel_columnas(leads):
    result = funnel_by_advisor(leads, leads)
    assert set(result.columns) == {"Asesor", "Asignados", "Calificados", "Cierres", "% Efic."}


def test_funnel_pct_efic_correcto(leads):
    result = funnel_by_advisor(leads, leads)
    sofia = result[result["Asesor"] == "Sofia"].iloc[0]
    # Sofia: 2 asignados, 1 cierre en abril → 50.0 %
    assert sofia["Cierres"] == 1
    assert sofia["% Efic."] == pytest.approx(50.0)


def test_funnel_asesor_sin_cierres(leads):
    result = funnel_by_advisor(leads, leads)
    # Ana no tiene cierres → no aparece en el resultado
    assert "Ana" not in result["Asesor"].values


def test_funnel_sin_propietario_no_aparece():
    df = pd.DataFrame([{
        "creado": datetime(2026, 4, 1),
        "propietario": None,
        "Motivo de no cierre": None,
        "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT,
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }])
    result = funnel_by_advisor(df, df)
    assert result.empty


def test_funnel_total_cierres_cuadra_con_kpi(leads):
    """funnel['Cierres'].sum() debe igualar metrics.total_cierres cuando no hay multi-cierre en el mes."""
    from src.analytics.metrics import compute_all_metrics
    metrics = compute_all_metrics(leads, leads)
    funnel = funnel_by_advisor(leads, leads)
    assert int(funnel["Cierres"].sum()) == metrics.total_cierres


def test_funnel_lead_sin_propietario_aparece_como_sin_asesor():
    """Un lead sin propietario que tiene cierre debe aparecer como 'Sin asesor'."""
    df = pd.DataFrame([{
        "creado": datetime(2026, 4, 1),
        "propietario": None,
        "Motivo de no cierre": None,
        "Cantidad de cierres": 1.0,
        "Fecha de cierre": datetime(2026, 4, 10),
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }])
    result = funnel_by_advisor(df, df)
    assert len(result) == 1
    assert result.iloc[0]["Asesor"] == "Sin asesor"
    assert result.iloc[0]["Cierres"] == 1


def test_funnel_excluye_asesores_sin_cierres():
    """Con 2 asesores y solo 1 con cierres, el resultado tiene solo 1 fila."""
    df = pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "carlos",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 10),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 4, 2),
            "propietario": "laura",
            "Motivo de no cierre": "no se logró contactar",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])
    result = funnel_by_advisor(df, df)
    assert len(result) == 1
    assert result.iloc[0]["Asesor"] == "Carlos"
