"""Tests para el desglose de cierres por 'Campaña - pauta'."""
from datetime import datetime

import pandas as pd

from src.analytics.closures_by_campaign import closures_by_campaign

_BASE = {
    "propietario": "sofia", "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
    "estado": "activo",
    "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT,
    "Fecha de 4to cierre": pd.NaT,
}


def _lead(campana, fecha_cierre, canal_offline="clientify - facebook", origen="facebook", estado="activo"):
    return {
        **_BASE,
        "creado": datetime(2026, 4, 1),
        "canal online": "paid social",
        "Canal offline": canal_offline,
        "Origen de la pauta": origen,
        "estado": estado,
        "Campaña - pauta": campana,
        "Fecha de cierre": fecha_cierre,
    }


def test_agrupa_cierres_por_campana():
    df = pd.DataFrame([
        _lead("INT_USA_ES_VID_WP_MAYO2026", datetime(2026, 4, 5)),
        _lead("INT_USA_ES_VID_WP_MAYO2026", datetime(2026, 4, 10)),
        _lead("CP_USA_ES_VID_FORM_MAYO2026", datetime(2026, 4, 15)),
    ])
    out = closures_by_campaign(df, 2026, 4)
    assert list(out["Campaña"]) == ["INT_USA_ES_VID_WP_MAYO2026", "CP_USA_ES_VID_FORM_MAYO2026"]
    assert list(out["Total"]) == [2, 1]
    assert out["Porcentaje"].sum() == 100.0


def test_filtra_por_mes():
    df = pd.DataFrame([
        _lead("CAMPANA_ABRIL", datetime(2026, 4, 5)),
        _lead("CAMPANA_MARZO", datetime(2026, 3, 5)),
    ])
    out = closures_by_campaign(df, 2026, 4)
    assert list(out["Campaña"]) == ["CAMPANA_ABRIL"]


def test_excluye_estado_inactivo():
    df = pd.DataFrame([
        _lead("CAMPANA_X", datetime(2026, 4, 5), estado="inactivo"),
    ])
    out = closures_by_campaign(df, 2026, 4)
    assert out.empty


def test_leads_sin_campana_van_a_sin_campana():
    df = pd.DataFrame([
        _lead(None, datetime(2026, 4, 5)),
        _lead("", datetime(2026, 4, 6)),
    ])
    out = closures_by_campaign(df, 2026, 4)
    assert list(out["Campaña"]) == ["Sin campaña"]
    assert list(out["Total"]) == [2]


def test_filtra_por_equipo_marketing_vs_referidos():
    df = pd.DataFrame([
        _lead("CAMPANA_PAUTA", datetime(2026, 4, 5), canal_offline="clientify - facebook", origen="facebook"),
        _lead("CAMPANA_REF", datetime(2026, 4, 6), canal_offline="referido externo", origen=None),
    ])
    solo_pauta = closures_by_campaign(df, 2026, 4, team="Marketing (pautas)")
    assert list(solo_pauta["Campaña"]) == ["CAMPANA_PAUTA"]

    solo_referidos = closures_by_campaign(df, 2026, 4, team="Referidos")
    assert list(solo_referidos["Campaña"]) == ["CAMPANA_REF"]


def test_suma_las_4_columnas_de_cierre():
    lead = {
        **_BASE,
        "creado": datetime(2026, 3, 1),
        "canal online": "paid social",
        "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook",
        "Campaña - pauta": "CAMPANA_RECIERRE",
        "Fecha de cierre": datetime(2026, 3, 5),
        "Fecha de segundo cierre": datetime(2026, 4, 10),
    }
    df = pd.DataFrame([lead])
    out = closures_by_campaign(df, 2026, 4)
    assert list(out["Campaña"]) == ["CAMPANA_RECIERRE"]
    assert list(out["Total"]) == [1]  # solo el 2do cierre cae en abril


def test_columna_ausente_devuelve_vacio():
    df = pd.DataFrame([{
        "creado": datetime(2026, 4, 1), "estado": "activo",
        "Fecha de cierre": datetime(2026, 4, 5),
    }])
    out = closures_by_campaign(df, 2026, 4)
    assert out.empty


def test_df_vacio_devuelve_vacio():
    out = closures_by_campaign(pd.DataFrame(), 2026, 4)
    assert out.empty
