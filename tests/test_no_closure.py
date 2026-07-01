"""Tests para src/analytics/no_closure.py."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.no_closure import (
    available_advisors_in_period,
    motive_distribution_filtered,
    qualified_vs_unqualified,
)


@pytest.fixture
def df_leads():
    """
    4 leads: sofia cerró en abril (Fecha de cierre), ana no cerró.
    """
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
        },
        {
            "creado": datetime(2026, 4, 4),
            "propietario": "ana",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])


# ---------------------------------------------------------------------------
# qualified_vs_unqualified
# ---------------------------------------------------------------------------

def test_qualified_vs_unqualified_claves(df_leads):
    result = qualified_vs_unqualified(df_leads)
    assert "Calificados" in result
    assert "No calificados" in result


def test_qualified_vs_unqualified_suma_total(df_leads):
    result = qualified_vs_unqualified(df_leads)
    assert result["Calificados"] + result["No calificados"] == 4


def test_qualified_vs_unqualified_por_asesor(df_leads):
    result = qualified_vs_unqualified(df_leads, asesor="ana")
    assert result["Calificados"] == 1
    assert result["No calificados"] == 1


# ---------------------------------------------------------------------------
# motive_distribution_filtered
# ---------------------------------------------------------------------------

def test_motive_distribution_filtered_filtra_por_mes_y_asesor():
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Ana", "Motivo de no cierre": "cliente potencial"},
        {"creado": pd.Timestamp("2026-04-15"), "propietario": "Ana", "Motivo de no cierre": ""},
        {"creado": pd.Timestamp("2026-04-20"), "propietario": "Juan", "Motivo de no cierre": "no se logró contactar"},
        {"creado": pd.Timestamp("2026-03-10"), "propietario": "Ana", "Motivo de no cierre": "cliente potencial"},
    ])
    result = motive_distribution_filtered(df, 2026, 4, "Ana")
    assert len(result) == 2   # "cliente potencial" + "Sin diligenciar"
    assert int(result["Cantidad"].sum()) == 2


def test_motive_distribution_filtered_motivos_vacios_son_sin_diligenciar():
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Ana", "Motivo de no cierre": ""},
        {"creado": pd.Timestamp("2026-04-02"), "propietario": "Ana", "Motivo de no cierre": None},
        {"creado": pd.Timestamp("2026-04-03"), "propietario": "Ana", "Motivo de no cierre": "nan"},
    ])
    result = motive_distribution_filtered(df, 2026, 4, "Todos")
    assert len(result) == 1
    assert result.iloc[0]["Motivo"] == "Sin diligenciar"
    assert int(result.iloc[0]["Cantidad"]) == 3


def test_motive_distribution_filtered_todos_incluye_todos_los_asesores():
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Ana", "Motivo de no cierre": "cliente potencial"},
        {"creado": pd.Timestamp("2026-04-02"), "propietario": "Juan", "Motivo de no cierre": "cliente potencial"},
    ])
    result = motive_distribution_filtered(df, 2026, 4, None)
    assert int(result["Cantidad"].sum()) == 2


# ---------------------------------------------------------------------------
# available_advisors_in_period
# ---------------------------------------------------------------------------

def test_available_advisors_solo_los_del_periodo():
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Ana"},
        {"creado": pd.Timestamp("2026-03-01"), "propietario": "Juan"},
    ])
    advisors = available_advisors_in_period(df, 2026, 4)
    assert "Ana" in advisors
    assert "Juan" not in advisors
