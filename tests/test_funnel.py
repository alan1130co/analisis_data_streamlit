"""Tests para src/analytics/funnel.py."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.funnel import funnel_by_advisor

_EXPECTED_COLUMNS = {
    "Asesor", "Asignados", "Calificados", "Cierres Pauta",
    "Cierres Totales", "% Eficiencia Real", "% Efic. Bruta",
    "Valor Pauta", "Valor Total del Proceso",
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


def test_funnel_ordenado_planta_por_eficiencia_no_planta_por_cierres_cesar_al_final():
    """Regla 2026-09-04 (invierte el orden de los grupos 1 y 2 de la versión
    anterior, el criterio interno de cada grupo no cambió): el orden es por
    3 grupos.
      1. Asesores de planta (PLANTA_ADVISORS) primero, ordenados por
         '% Efic. Bruta' descendente — para ellos sí tiene sentido: su
         'Asignados' es real.
      2. 'Todos los demás' (no-planta, no-César), ordenados por 'Cierres
         Totales' descendente — NO por '% Efic. Bruta', porque ese campo
         siempre da 0.0 para este grupo ('Asignados' es 0 por construcción)
         y no los distinguiría entre sí.
      3. César Augusto, siempre en la última fila de toda la tabla, sin
         importar su valor (aunque sea el más alto de la tabla).
    """
    df = pd.DataFrame([
        # No-planta, Cierres Totales=2 (2 cierres válidos en abril) → debe ir
        # primero dentro del grupo "todos los demás" (que ahora va 2do, después de planta).
        {
            "creado": datetime(2026, 4, 1), "propietario": "carlos ruiz", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 2),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": "referido - amigo", "Origen de la pauta": None,
        },
        {
            "creado": datetime(2026, 4, 3), "propietario": "carlos ruiz", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": datetime(2026, 4, 10),
            "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": "referido - amigo", "Origen de la pauta": None,
        },
        # No-planta, Cierres Totales=1 → debe ir después de Carlos (2) y antes de Elena (0).
        {
            "creado": datetime(2026, 4, 1), "propietario": "diana torres", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 3),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        # No-planta, Cierres Totales=0 (asignada pero sin cierre) → última del grupo.
        {
            "creado": datetime(2026, 4, 1), "propietario": "elena vidal", "estado": "en transito",
            "Motivo de no cierre": None, "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        },
        # Planta (Ana Perdomo): 2 asignados, 1 cierre de pauta → % Efic. Bruta = 50.0
        {
            "creado": datetime(2026, 4, 2), "propietario": "ana perdomo", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        {
            "creado": datetime(2026, 4, 3), "propietario": "ana perdomo", "estado": "en transito",
            "Motivo de no cierre": None, "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        },
        # Planta (Sofía De La Hoz, con tilde a propósito — prueba la
        # normalización sin acentos): 4 asignados, 1 cierre de pauta →
        # % Efic. Bruta = 25.0, menor que Ana → debe ir después de ella.
        {
            "creado": datetime(2026, 4, 2), "propietario": "sofía de la hoz", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 6),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        *[
            {
                "creado": datetime(2026, 4, d), "propietario": "sofía de la hoz", "estado": "en transito",
                "Motivo de no cierre": None, "Cantidad de cierres": None,
                "Fecha de cierre": pd.NaT,
                "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
                "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
            }
            for d in (7, 8, 9)
        ],
        # César Augusto: NO está en PLANTA_ADVISORS pero mantiene Asignados
        # real (excepción explícita) — 1 asignado, 1 cierre → % Efic. Bruta
        # = 100.0, el valor MÁS ALTO de la tabla, pero igual debe ir último
        # porque el agrupamiento manda sobre el valor numérico.
        {
            "creado": datetime(2026, 4, 2), "propietario": "cesar augusto perez tafur", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 7),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
    ])

    result = funnel_by_advisor(df, df, 2026, 4)

    assert list(result["Asesor"]) == [
        "Ana Perdomo", "Sofía De La Hoz",
        "Carlos Ruiz", "Diana Torres", "Elena Vidal",
        "Cesar Augusto Perez Tafur",
    ]
    # Grupo planta: % Efic. Bruta descendente (50, 25).
    assert list(result["% Efic. Bruta"])[:2] == [50.0, 25.0]
    # Grupo "todos los demás": Cierres Totales descendente (2, 1, 0).
    assert list(result["Cierres Totales"])[2:5] == [2, 1, 0]
    # César último con % Efic. Bruta=100.0 pese a ser el valor más alto de
    # toda la tabla — el agrupamiento manda sobre el valor numérico.
    assert list(result["% Efic. Bruta"])[5:] == [100.0]


def test_funnel_columnas(leads):
    result = funnel_by_advisor(leads, leads, 2026, 4)
    assert set(result.columns) == _EXPECTED_COLUMNS


@pytest.fixture
def lead_referido_sin_cierres():
    """Un asesor explícitamente NO de planta y NO César, sin cierres — el
    caso típico de un lead 'referido' que no pasa por PLANTA_ADVISORS."""
    return pd.DataFrame([{
        "creado": datetime(2026, 4, 2),
        "propietario": "carla martinez",
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
    }])


def test_funnel_asesor_referido_sin_cierres_asignados_cero(lead_referido_sin_cierres):
    """Carla (no planta, no César) no tiene cierres pero SÍ tiene un lead
    asignado → debe aparecer igual (regla 2026-07-15). Su 'Asignados' da 0
    porque no está en PLANTA_ADVISORS ni es César — comportamiento ESPERADO
    de la regla 2026-09-03 (Cambio 1), no un bug."""
    result = funnel_by_advisor(lead_referido_sin_cierres, lead_referido_sin_cierres, 2026, 4)
    carla = result[result["Asesor"] == "Carla Martinez"].iloc[0]
    assert carla["Asignados"] == 0
    assert carla["Calificados"] == 0
    assert carla["Cierres Pauta"] == 0
    assert carla["Cierres Totales"] == 0
    assert carla["% Eficiencia Real"] == 0.0
    assert carla["% Efic. Bruta"] == 0.0


def test_funnel_cierres_pauta_y_totales_y_eficiencias():
    """Valida Cierres Pauta/Totales y las 2 eficiencias en ambos casos: un
    asesor de planta (Asignados real, denominador > 0 en % Efic. Bruta) y un
    asesor no-planta (Asignados forzado a 0 → % Efic. Bruta da 0.0 aunque
    tenga un cierre real, regla 2026-09-03 / Cambio 1)."""
    df = pd.DataFrame([
        # Ana Perdomo (planta): 2 asignados. Regla estricta (2026-08-12c): el
        # 1er lead califica (motivo="cliente potencial", diligenciado); el
        # 2do lead (motivo vacío, sin cierre) NO califica → 1 calificado, no 2.
        # 1 cierre (facebook → Pauta).
        {
            "creado": datetime(2026, 4, 1), "propietario": "ana perdomo", "estado": "activo",
            "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        {
            "creado": datetime(2026, 4, 3), "propietario": "ana perdomo", "estado": "en transito",
            "Motivo de no cierre": None, "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        # "ana" (NO planta — es solo el primer nombre, no matchea "ana
        # perdomo" normalizado): 1 asignado real y 1 cierre de pauta real,
        # pero Asignados se fuerza a 0 → % Efic. Bruta da 0.0 pese al cierre.
        {
            "creado": datetime(2026, 4, 2), "propietario": "ana", "estado": "activo",
            "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 8),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
    ])

    result = funnel_by_advisor(df, df, 2026, 4)

    ana_perdomo = result[result["Asesor"] == "Ana Perdomo"].iloc[0]
    assert ana_perdomo["Asignados"] == 2
    assert ana_perdomo["Calificados"] == 1
    assert ana_perdomo["Cierres Pauta"] == 1
    assert ana_perdomo["Cierres Totales"] == 1
    # % Eficiencia Real = (1 * 100) / 1 calificado = 100.0
    assert ana_perdomo["% Eficiencia Real"] == pytest.approx(100.0)
    # % Efic. Bruta = (1 * 100) / 2 asignados = 50.0 (Asignados real, es planta)
    assert ana_perdomo["% Efic. Bruta"] == pytest.approx(50.0)

    ana = result[result["Asesor"] == "Ana"].iloc[0]
    assert ana["Asignados"] == 0
    assert ana["Calificados"] == 1  # el cierre real cuenta como calificado, no depende de Asignados
    assert ana["Cierres Pauta"] == 1
    assert ana["Cierres Totales"] == 1
    # % Eficiencia Real usa Calificados (no Asignados), así que no se ve afectada
    assert ana["% Eficiencia Real"] == pytest.approx(100.0)
    # % Efic. Bruta SÍ usa Asignados → forzado a 0.0 pese al cierre real
    assert ana["% Efic. Bruta"] == 0.0


def test_funnel_cesar_augusto_mantiene_asignados_real_sin_estar_en_planta():
    """César Augusto no está en PLANTA_ADVISORS pero es una excepción
    explícita de la regla 2026-09-03: su 'Asignados' refleja el conteo real
    de leads creados en el período, igual que un asesor de planta."""
    df = pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1), "propietario": "césar augusto pérez tafur", "estado": "activo",
            "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 4),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
        },
        {
            "creado": datetime(2026, 4, 2), "propietario": "césar augusto pérez tafur", "estado": "en transito",
            "Motivo de no cierre": None, "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        },
        {
            "creado": datetime(2026, 4, 3), "propietario": "césar augusto pérez tafur", "estado": "en transito",
            "Motivo de no cierre": None, "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        },
    ])
    result = funnel_by_advisor(df, df, 2026, 4)
    cesar = result[result["Asesor"] == "César Augusto Pérez Tafur"].iloc[0]
    assert cesar["Asignados"] == 3
    assert cesar["Cierres Pauta"] == 1
    # % Efic. Bruta = (1 * 100) / 3 asignados = 33.3 (Asignados real, es César)
    assert cesar["% Efic. Bruta"] == pytest.approx(33.3)


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
    assert result.iloc[0]["% Efic. Bruta"] == 0.0


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


# ---------------------------------------------------------------------------
# Valor Pauta / Valor Total del Proceso
# ---------------------------------------------------------------------------

def test_funnel_valor_total_del_proceso_formato_europeo_miles_decimales():
    """_clean_importe debe interpretar '1.500,00' como 1500.00 (formato
    europeo: '.' separador de miles, ',' decimal) — mismo parseo que ya usa
    ad_spend_vs_closures.py para estas mismas columnas."""
    df = pd.DataFrame([{
        "creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": "activo",
        "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
        "Fecha de cierre": datetime(2026, 4, 5),
        "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook",
        "Valor total del proceso": "1.500,00",
    }])
    result = funnel_by_advisor(df, df, 2026, 4)
    sofia = result[result["Asesor"] == "Sofia"].iloc[0]
    assert sofia["Valor Total del Proceso"] == pytest.approx(1500.00)
    assert sofia["Valor Pauta"] == pytest.approx(1500.00)  # facebook → Pauta


def test_funnel_valor_total_del_proceso_suma_1er_y_2do_cierre():
    """Un lead con 1er y 2do cierre en el mismo mes debe sumar AMBOS campos
    de valor por separado ('Valor total del proceso' + 'Valor total segundo
    cierre') — NO reutilizar el valor del 1er cierre para el 2do, que es el
    bug conocido y documentado de revenue_from_redes_monthly en
    ad_spend_vs_closures.py, no reproducido acá (usa _STAGE_VALUE_COLS,
    cada etapa con su propio campo)."""
    df = pd.DataFrame([{
        "creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": "activo",
        "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 2.0,
        "Fecha de cierre": datetime(2026, 4, 5),
        "Fecha de segundo cierre": datetime(2026, 4, 20),
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook",
        "Valor total del proceso": "1000",
        "Valor total segundo cierre": "2000",
    }])
    result = funnel_by_advisor(df, df, 2026, 4)
    sofia = result[result["Asesor"] == "Sofia"].iloc[0]
    # 1000 (1er cierre) + 2000 (2do cierre) = 3000. Si se reutilizara el
    # valor del 1er cierre para el 2do, daría 2000 (1000+1000) en vez de 3000.
    assert sofia["Valor Total del Proceso"] == pytest.approx(3000.0)


def test_funnel_valor_pauta_es_subconjunto_de_valor_total():
    """Valor Pauta debe sumar SOLO los cierres clasificados Pauta
    (is_marketing), mientras Valor Total del Proceso suma Pauta + Referidos
    — mismo desglose que ya existe para Cierres Pauta/Cierres Totales."""
    df = pd.DataFrame([
        {  # Pauta (facebook)
            "creado": datetime(2026, 4, 1), "propietario": "carla", "estado": "activo",
            "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
            "Valor total del proceso": "1000",
        },
        {  # Referido puro
            "creado": datetime(2026, 4, 2), "propietario": "carla", "estado": "activo",
            "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 6),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "inbox", "Canal offline": "referido - amigo",
            "Origen de la pauta": None,
            "Valor total del proceso": "500",
        },
    ])
    result = funnel_by_advisor(df, df, 2026, 4)
    carla = result[result["Asesor"] == "Carla"].iloc[0]
    assert carla["Valor Pauta"] == pytest.approx(1000.0)
    assert carla["Valor Total del Proceso"] == pytest.approx(1500.0)
    assert carla["Valor Pauta"] <= carla["Valor Total del Proceso"]


def test_funnel_valor_total_del_proceso_respeta_el_mes_filtrado():
    """Un cierre fuera del mes filtrado (marzo, al pedir abril) no debe
    sumar; el mismo asesor con un cierre dentro del mes sí debe sumar —
    mismo criterio de período que ya usa Cierres Totales."""
    df = pd.DataFrame([
        {  # cierre en marzo → NO debe sumar al pedir abril
            "creado": datetime(2026, 3, 1), "propietario": "sofia", "estado": "activo",
            "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 3, 15),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
            "Valor total del proceso": "9999",
        },
        {  # cierre en abril → SÍ debe sumar
            "creado": datetime(2026, 4, 2), "propietario": "sofia", "estado": "activo",
            "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 10),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
            "Valor total del proceso": "700",
        },
    ])
    result = funnel_by_advisor(df, df, 2026, 4)
    sofia = result[result["Asesor"] == "Sofia"].iloc[0]
    assert sofia["Valor Total del Proceso"] == pytest.approx(700.0)
