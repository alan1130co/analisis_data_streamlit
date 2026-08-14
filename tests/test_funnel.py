"""Tests para src/analytics/funnel.py."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.funnel import funnel_by_advisor

_EXPECTED_COLUMNS = {
    "Asesor", "Asignados", "Calificados", "Cierres Pauta",
    "Cierres Totales", "% Eficiencia Real", "% Efic. Global",
}


@pytest.fixture
def leads():
    return pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "sofia",
            "estado": "activo",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        {
            "creado": datetime(2026, 4, 2),
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
            "creado": datetime(2026, 4, 3),
            "propietario": "sofia",
            "estado": "en transito",
            "Motivo de no cierre": None,
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
    ])


def test_funnel_incluye_todos_los_asesores_con_asignados(leads):
    """Todo asesor con >=1 lead asignado aparece, tenga o no cierres."""
    result = funnel_by_advisor(leads, leads, 2026, 4)
    assert set(result["Asesor"]) == {"Sofia", "Ana"}


def test_funnel_ordenado_por_asignados(leads):
    result = funnel_by_advisor(leads, leads, 2026, 4)
    assert result.iloc[0]["Asesor"] == "Sofia"
    assert result.iloc[0]["Asignados"] == 2


def test_funnel_columnas(leads):
    result = funnel_by_advisor(leads, leads, 2026, 4)
    assert set(result.columns) == _EXPECTED_COLUMNS


def test_funnel_asesor_sin_cierres_aparece_con_ceros(leads):
    """Ana no tiene cierres pero SÍ tiene un lead asignado → debe aparecer."""
    result = funnel_by_advisor(leads, leads, 2026, 4)
    ana = result[result["Asesor"] == "Ana"].iloc[0]
    assert ana["Asignados"] == 1
    assert ana["Cierres Pauta"] == 0
    assert ana["Cierres Totales"] == 0
    assert ana["% Eficiencia Real"] == 0.0
    assert ana["% Efic. Global"] == 0.0


def test_funnel_cierres_pauta_y_totales_y_eficiencias(leads):
    result = funnel_by_advisor(leads, leads, 2026, 4)
    sofia = result[result["Asesor"] == "Sofia"].iloc[0]
    # Sofia: 2 asignados. Regla estricta (2026-08-12c): el 1er lead califica
    # (motivo="cliente potencial", diligenciado); el 3er lead (motivo vacío,
    # sin cierre) ya NO califica → 1 calificado, no 2. 1 cierre (facebook → Pauta).
    assert sofia["Calificados"] == 1
    assert sofia["Cierres Pauta"] == 1
    assert sofia["Cierres Totales"] == 1
    # % Eficiencia Real = (1 * 100) / 1 calificado = 100.0
    assert sofia["% Eficiencia Real"] == pytest.approx(100.0)
    # % Efic. Global = (1 * 100) / 2 asignados = 50.0 (no depende de calificados)
    assert sofia["% Efic. Global"] == pytest.approx(50.0)


def test_funnel_sin_propietario_no_aparece_sin_cierres():
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
    result = funnel_by_advisor(df, df, 2026, 4)
    assert result.empty


def test_funnel_lead_sin_propietario_aparece_como_sin_asesor():
    """Un lead sin propietario que tiene cierre debe aparecer como 'Sin asesor'."""
    df = pd.DataFrame([{
        "creado": datetime(2026, 4, 1),
        "propietario": None,
        "estado": "activo",
        "Motivo de no cierre": None,
        "Cantidad de cierres": 1.0,
        "Fecha de cierre": datetime(2026, 4, 10),
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
        "canal online": "inbox",
        "Canal offline": None,
        "Origen de la pauta": None,
    }])
    result = funnel_by_advisor(df, df, 2026, 4)
    assert len(result) == 1
    assert result.iloc[0]["Asesor"] == "Sin asesor"
    assert result.iloc[0]["Cierres Totales"] == 1
    assert result.iloc[0]["% Efic. Global"] == 0.0


def test_funnel_asesor_independiente_sin_cierres_aparece():
    """Regla 2026-07-15: asesores independientes/free con 0 cierres deben
    listarse igual, mientras tengan >=1 lead asignado en el período."""
    df = pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "margren lozano",
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
        {
            "creado": datetime(2026, 4, 2),
            "propietario": "juan rodriguez",
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
    result = funnel_by_advisor(df, df, 2026, 4)
    assert set(result["Asesor"]) == {"Margren Lozano", "Juan Rodriguez"}
    assert (result["Cierres Totales"] == 0).all()


def test_funnel_cierres_pauta_regla_redes_organico_tiktok_whatsapp():
    """Cierres Pauta debe capturar Canal offline con 'redes' (incl. 'Referido...Redes'),
    orgánico, tiktok, facebook, instagram, whatsapp — y Origen de la pauta equivalentes."""
    df = pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1), "propietario": "carla", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox-referral", "Canal offline": "referido cliente activo - redes",
            "Origen de la pauta": None,
        },
        {
            "creado": datetime(2026, 4, 2), "propietario": "carla", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 6),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": "whatsapp",
            "Origen de la pauta": None,
        },
        {
            "creado": datetime(2026, 4, 3), "propietario": "carla", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 7),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": "referido - amigo",
            "Origen de la pauta": None,
        },
    ])
    result = funnel_by_advisor(df, df, 2026, 4)
    carla = result[result["Asesor"] == "Carla"].iloc[0]
    # Las 2 primeras (redes, whatsapp) son Pauta; la 3ra (referido puro) no.
    assert carla["Cierres Pauta"] == 2
    assert carla["Cierres Totales"] == 3


def test_funnel_total_cierres_cuadra_con_kpi(leads):
    """funnel['Cierres Totales'].sum() debe igualar metrics.total_cierres_general."""
    from src.analytics.metrics import compute_all_metrics
    metrics = compute_all_metrics(leads, leads)
    funnel = funnel_by_advisor(leads, leads, 2026, 4)
    assert int(funnel["Cierres Totales"].sum()) == metrics.total_cierres_general


def test_funnel_usa_el_periodo_explicito_no_lo_infiere_de_los_datos():
    """Bug de desincronización de fechas: funnel_by_advisor ya NO debe adivinar
    el período desde df_period['creado'] (con fallback a pd.Timestamp.now()) —
    debe usar exactamente el (year, month) que le pasa el caller/frontend,
    incluso si difiere del mes de los leads creados en df_period."""
    df_period = pd.DataFrame([{
        # Lead ASIGNADO en abril (para que el asesor aparezca en la tabla)...
        "creado": datetime(2026, 4, 1),
        "propietario": "carla", "estado": "activo",
        "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }])
    df_full = pd.DataFrame([
        df_period.iloc[0].to_dict(),
        {
            # ...pero su CIERRE ocurre en julio, un período distinto al de
            # creación. Si la función siguiera infiriendo el período desde
            # df_period (todo abril), este cierre de julio nunca se contaría
            # al pedir explícitamente year=2026, month=7.
            "creado": datetime(2026, 3, 5),
            "propietario": "carla", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 7, 10),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        },
    ])
    result_julio = funnel_by_advisor(df_period, df_full, 2026, 7)
    carla_julio = result_julio[result_julio["Asesor"] == "Carla"].iloc[0]
    assert carla_julio["Cierres Totales"] == 1

    result_abril = funnel_by_advisor(df_period, df_full, 2026, 4)
    carla_abril = result_abril[result_abril["Asesor"] == "Carla"].iloc[0]
    assert carla_abril["Cierres Totales"] == 0
