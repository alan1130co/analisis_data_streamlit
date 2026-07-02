"""
Test de integridad global: verifica que los totales cuadren entre secciones.

Fixture _make_period_and_full() cubre todos los escenarios:
  - Marketing con 1er cierre en el mes
  - Marketing con 2do cierre en el mes (lead creado en marzo)
  - Referidos (canal offline con prefijo "referido") con cierre
  - Referidos con Canal offline vacío y cierre, sin propietario
  - Lead sin cierre (activo)
  - Lead UNQUALIFIED (motivo explícito en UNQUALIFIED_MOTIVES)
"""
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import pytest

from src.analytics.metrics import compute_all_metrics, is_marketing
from src.analytics.breakdowns import cierres_por_canal, pauta_vs_referidos, efficiency_by_advisor
from src.analytics.funnel import funnel_by_advisor
from src.analytics.no_closure import qualified_vs_unqualified
from src.analytics.filters import filter_by_month
from src.data_sources.excel_loader import ExcelContactsLoader


_NaT = pd.NaT
_PERIOD = datetime(2026, 4, 1)
_CLOSE_NaT = {
    "Fecha de segundo cierre": _NaT,
    "Fecha de tercer cierre": _NaT,
    "Fecha de 4to cierre": _NaT,
}


def _make_period_and_full():
    """
    6 leads de abril + 1 lead de marzo (2do cierre en abril). Todos "activo"
    salvo donde se indique, para que sus cierres sean válidos.

    total_cierres_general esperado = 4:
      - Lead L1 (sofia, mkt):    Fecha de cierre = April 5
      - lead_march (sofia, mkt): Fecha de segundo cierre = April 10
      - Lead L2 (ana, ref):      Fecha de cierre = April 15
      - Lead L3 (None, sin canal): Fecha de cierre = April 20
    """
    lead_march = {
        "creado": datetime(2026, 3, 1), "propietario": "sofia", "estado": "activo",
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook", "Motivo de no cierre": None,
        "Cantidad de cierres": 2.0,
        "Fecha de cierre": datetime(2026, 3, 15),
        "Fecha de segundo cierre": datetime(2026, 4, 10),
        "Fecha de tercer cierre": _NaT, "Fecha de 4to cierre": _NaT,
    }
    leads_april = [
        # L1: Marketing, sofia, 1er cierre April 5
        {"creado": _PERIOD, "propietario": "sofia", "estado": "activo",
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5), **_CLOSE_NaT},
        # L2: Referido (canal con prefijo), ana, cierre April 15
        {"creado": _PERIOD, "propietario": "ana", "estado": "activo",
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 15), **_CLOSE_NaT},
        # L3: Referido (canal vacío), sin propietario, cierre April 20
        {"creado": _PERIOD, "propietario": None, "estado": "activo",
         "canal online": "inbox", "Canal offline": None,
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 20), **_CLOSE_NaT},
        # L4: Marketing, sofia, sin cierre, motivo vacío → calificado
        {"creado": _PERIOD, "propietario": "sofia", "estado": "en transito",
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT},
        # L5: Referido, ana, sin cierre, UNQUALIFIED → NO calificado
        {"creado": _PERIOD, "propietario": "ana", "estado": "en transito",
         "canal online": "inbox", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": "no se logró contactar",
         "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT},
    ]
    return pd.DataFrame(leads_april), pd.DataFrame([lead_march] + leads_april)


def test_totales_cuadran_entre_secciones():
    """
    total_cierres_general (todas las fuentes) debe coincidir con pauta_vs_referidos,
    cierres_por_canal (team=Todos) y funnel — todos suman las 4 columnas de cierre.

    (El KPI total_cierres, en cambio, es una métrica de negocio más angosta:
    solo Pauta + Orgánico, así que no se compara acá.)
    """
    df_period, df_full = _make_period_and_full()
    metrics = compute_all_metrics(df_period, df_full)
    expected = metrics.total_cierres_general  # 4

    pvr = pauta_vs_referidos(df_period, df_full)
    assert int(pvr["Cantidad"].sum()) == expected, \
        f"pauta_vs_referidos sumó {pvr['Cantidad'].sum()}, KPI dice {expected}"

    canal_todos = cierres_por_canal(df_period, df_full, team="Todos")
    assert int(canal_todos["Cantidad"].sum()) == expected, \
        f"cierres_por_canal team=Todos sumó {canal_todos['Cantidad'].sum()}, KPI dice {expected}"

    funnel = funnel_by_advisor(df_period, df_full)
    assert int(funnel["Cierres"].sum()) == expected, \
        f"funnel sumó {funnel['Cierres'].sum()}, KPI dice {expected}"


def test_calificados_consistente_entre_secciones():
    """
    Calificados del KPI debe coincidir con funnel, efficiency_by_advisor y qualified_vs_unqualified.

    Fixture diseñado para que TODOS los asesores tengan leads de marketing Y cierres,
    de modo que aparezcan en eff (only_with_closures=False) y en funnel.
    """
    df_period = pd.DataFrame([
        # sofia: mkt, cierra April, Motivo=None → calificado
        {"creado": _PERIOD, "propietario": "sofia", "estado": "activo",
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5), **_CLOSE_NaT},
        # sofia: mkt, sin cierre, UNQUALIFIED → NO calificado
        {"creado": _PERIOD, "propietario": "sofia", "estado": "en transito",
         "canal online": "inbox", "Canal offline": "clientify - facebook",
         "Origen de la pauta": None, "Motivo de no cierre": "no se logró contactar",
         "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT},
        # ana: mkt, cierra April, motivo calificado → calificado
        {"creado": _PERIOD, "propietario": "ana", "estado": "activo",
         "canal online": "paid social", "Canal offline": "clientify - instagram",
         "Origen de la pauta": "instagram", "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 10), **_CLOSE_NaT},
        # ana: mkt, sin cierre, Motivo=None → calificado
        {"creado": _PERIOD, "propietario": "ana", "estado": "en transito",
         "canal online": "paid social", "Canal offline": "clientify - instagram",
         "Origen de la pauta": "instagram", "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT},
    ])

    metrics = compute_all_metrics(df_period, df_period)
    # Expected: 3 calificados (Motivo=None ×2, QUALIFIED_MOTIVES ×1; UNQUALIFIED ×1 → NO)

    funnel = funnel_by_advisor(df_period, df_period)
    assert metrics.calificados == int(funnel["Calificados"].sum()), \
        f"KPI={metrics.calificados}, funnel={funnel['Calificados'].sum()}"

    eff = efficiency_by_advisor(df_period, df_period, only_with_closures=False)
    assert metrics.calificados == int(eff["Calificados"].sum()), \
        f"KPI={metrics.calificados}, efficiency={eff['Calificados'].sum()}"

    qvu = qualified_vs_unqualified(df_period)
    assert metrics.calificados == qvu["Calificados"], \
        f"KPI={metrics.calificados}, no_closure={qvu['Calificados']}"


def test_calificados_marketing_mas_referidos_igual_total():
    """Calificados(team=Todos) == Calificados(team=Marketing) + Calificados(team=Referidos)."""
    leads = [
        # Marketing, calificado (Motivo=None)
        {"creado": _PERIOD, "propietario": "sofia",
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5), **_CLOSE_NaT},
        # Marketing, NO calificado (UNQUALIFIED, sin cierre)
        {"creado": _PERIOD, "propietario": "ana",
         "canal online": "paid social", "Canal offline": "clientify - instagram",
         "Origen de la pauta": "instagram", "Motivo de no cierre": "no se logró contactar",
         "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT},
        # Referido (canal con prefijo), calificado (Motivo=None)
        {"creado": _PERIOD, "propietario": "carlos",
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 10), **_CLOSE_NaT},
        # Referido, calificado (QUALIFIED_MOTIVES)
        {"creado": _PERIOD, "propietario": "lucia",
         "canal online": "inbox", "Canal offline": "referido - cliente activo",
         "Origen de la pauta": None, "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT},
        # Referido (canal vacío/None), calificado (Motivo=None)
        {"creado": _PERIOD, "propietario": None,
         "canal online": "inbox", "Canal offline": None,
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT},
    ]
    df_all = pd.DataFrame(leads)
    mkt_mask = df_all.apply(is_marketing, axis=1)
    df_mkt = df_all[mkt_mask]
    df_ref = df_all[~mkt_mask]

    m_total = compute_all_metrics(df_all, df_all).calificados  # 4 (leads 0, 2, 3, 4)
    m_mkt = compute_all_metrics(df_mkt, df_mkt).calificados    # 1 (lead 0)
    m_ref = compute_all_metrics(df_ref, df_ref).calificados    # 3 (leads 2, 3, 4)
    assert m_total == m_mkt + m_ref, \
        f"Todos={m_total}, Marketing={m_mkt}, Referidos={m_ref}, suma={m_mkt + m_ref}"


def test_calificado_motivo_vacio_cuenta():
    """Motivo vacío o None → CALIFICADO; motivo en UNQUALIFIED_MOTIVES sin cierre → NO calificado."""
    _base = {
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        "Cantidad de cierres": None, "Fecha de cierre": _NaT, **_CLOSE_NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": _PERIOD, "propietario": "Sofia", "Motivo de no cierre": ""},
        {**_base, "creado": _PERIOD, "propietario": "Ana",   "Motivo de no cierre": None},
        {**_base, "creado": _PERIOD, "propietario": "Carlos", "Motivo de no cierre": "no se logró contactar"},
    ])
    metrics = compute_all_metrics(df, df)
    assert metrics.calificados == 2, \
        f"Esperado 2 calificados ('' y None), obtenido {metrics.calificados}"


def test_calificados_motivo_vacio_cuenta_en_las_3_vistas():
    """
    Un lead con Motivo de no cierre vacío debe contar como calificado
    en Marketing, Referidos y Todos — las 3 vistas usan is_qualified_mask.
    """
    df = pd.DataFrame([
        # Marketing, motivo vacío → calificado en pauta
        {
            "creado": pd.Timestamp("2026-04-01"),
            "Canal offline": "Clientify - Whatsapp",
            "canal online": "paid social",
            "Motivo de no cierre": "",
            "Cantidad de cierres": None,
            "propietario": "Ana",
        },
        # Referido, motivo None → calificado en referidos
        {
            "creado": pd.Timestamp("2026-04-02"),
            "Canal offline": "Referido externo",
            "canal online": "inbox-referral",
            "Motivo de no cierre": None,
            "Cantidad de cierres": None,
            "propietario": "Juan",
        },
        # Marketing, UNQUALIFIED → NO calificado
        {
            "creado": pd.Timestamp("2026-04-03"),
            "Canal offline": "Clientify - Facebook",
            "canal online": "paid social",
            "Motivo de no cierre": "no se logró contactar",
            "Cantidad de cierres": None,
            "propietario": "Ana",
        },
    ])

    metrics = compute_all_metrics(df, df)

    assert metrics.calificados == 2, \
        f"Total calificados esperado=2, obtenido={metrics.calificados}"
    assert metrics.calificados_pauta == 1, \
        f"Calificados pauta esperado=1, obtenido={metrics.calificados_pauta}"
    assert metrics.calificados_referido == 1, \
        f"Calificados referido esperado=1, obtenido={metrics.calificados_referido}"


def test_april_2026_numeros_reales_verificados_manualmente():
    """Validación contra la base real, tras las correcciones de negocio:

    - Un cierre solo es válido si el lead está Activo (o Activo - mora).
    - Se corrigió la fuga de referidos ("Referido cliente activo - Redes" ya
      no cuenta como Pauta por contener la palabra "redes").
    - TikTok y Orgánico son categorías propias, ya no se cuentan como Pauta.
    - Origen de la pauta (Facebook/Instagram) prevalece sobre canal
      online=inbox-referral (Click-to-Message).

    Números recalculados con clientify_contactos_03_06_2026.xls. Si se carga
    otro archivo, actualizar estos valores.
    """
    raw_dir = Path("data/raw")
    files = sorted(raw_dir.glob("*.xls*"))
    if not files:
        pytest.skip("No hay archivo en data/raw/ para test de integridad")

    df = ExcelContactsLoader(str(files[-1])).load()
    df_april = filter_by_month(df, date(2026, 4, 1))
    metrics = compute_all_metrics(df_april, df)

    assert metrics.cierres_pauta_primer == 16, f"cierres_pauta_primer={metrics.cierres_pauta_primer}, esperado 16"
    assert metrics.cierres_referido_primer == 10, f"cierres_referido_primer={metrics.cierres_referido_primer}, esperado 10"
    assert metrics.cierres_adicionales_pauta == 2, f"adicionales pauta={metrics.cierres_adicionales_pauta}, esperado 2"
    assert metrics.cierres_adicionales_referido == 5, f"adicionales referido={metrics.cierres_adicionales_referido}, esperado 5"

    # === total_cierres (KPI) = solo Pauta + Orgánico, válidos, suma 1+2+3+4 ===
    assert metrics.total_cierres == 18, f"total_cierres={metrics.total_cierres}, esperado 18"
    assert metrics.cierres_marketing == 18, f"cierres_marketing={metrics.cierres_marketing}, esperado 18"
    assert metrics.cierres_referidos == 15, f"cierres_referidos={metrics.cierres_referidos}, esperado 15"
    # total_cierres_general = todas las fuentes (Pauta+Orgánico+TikTok+Referidos)
    assert metrics.total_cierres_general == 33, f"total_cierres_general={metrics.total_cierres_general}, esperado 33"

    # === Cierres por canal cuadran con totales (válidos, suma 1+2+3+4) ===
    canal_todos = cierres_por_canal(df_april, df, team="Todos")
    canal_marketing = cierres_por_canal(df_april, df, team="Marketing (pautas)")

    assert int(canal_todos["Cantidad"].sum()) == 33, \
        f"canal Todos suma {canal_todos['Cantidad'].sum()}, esperado 33"
    assert int(canal_marketing["Cantidad"].sum()) == 18, \
        f"canal Marketing suma {canal_marketing['Cantidad'].sum()}, esperado 18"


def test_april_2026_creados_y_calificados_marketing():
    """Validación de los números reales de Marketing en abril 2026."""
    raw_dir = Path("data/raw")
    files = sorted(raw_dir.glob("*.xls*"))
    if not files:
        pytest.skip("No hay archivo en data/raw/")

    df = ExcelContactsLoader(str(files[-1])).load()
    df_april = filter_by_month(df, date(2026, 4, 1))
    metrics = compute_all_metrics(df_april, df)

    # Números verificados con clientify_contactos_03_06_2026.xls (archivo actual en data/raw/)
    # Si se carga otro archivo, actualizar estos valores.
    assert metrics.creados == 595
    assert metrics.creados_pauta == 90, f"creados_pauta={metrics.creados_pauta}, esperado 90"
    assert metrics.creados_referido == 505, f"creados_referido={metrics.creados_referido}, esperado 505"
    assert metrics.calificados_pauta == 66, f"calificados_pauta={metrics.calificados_pauta}, esperado 66"
    assert metrics.no_calificados_pauta == 24, f"no_calificados_pauta={metrics.no_calificados_pauta}, esperado 24"
    assert metrics.calificados_pauta + metrics.no_calificados_pauta == metrics.creados_pauta

    # === Nuevas tarjetas: Leads Pauta/Orgánico/TikTok, Asignados, Eficiencias ===
    assert metrics.leads_pauta == 90
    assert metrics.leads_organico == 0
    assert metrics.leads_tiktok == 2
    assert metrics.asignados == 594  # todos los propietarios menos cuentas no comerciales
    assert metrics.asignados_pauta == 90


def test_may_2026_numeros_reales_verificados():
    """Validación contra base real de mayo 2026, tras las correcciones de negocio
    (Activo, fuga de referidos, TikTok/Orgánico separados, Origen de pauta prioritario)."""
    raw_dir = Path("data/raw")
    files = sorted(raw_dir.glob("*.xls*"))
    if not files:
        pytest.skip("No hay archivo en data/raw/")

    df = ExcelContactsLoader(str(files[-1])).load()
    df_mayo = filter_by_month(df, date(2026, 5, 1))
    metrics = compute_all_metrics(df_mayo, df)

    assert metrics.total_cierres == 23, f"total_cierres={metrics.total_cierres}, esperado 23"
    assert metrics.cierres_marketing == 22, f"cierres_marketing={metrics.cierres_marketing}, esperado 22"
    assert metrics.cierres_referidos == 15, f"cierres_referidos={metrics.cierres_referidos}, esperado 15"
    assert metrics.total_cierres_general == 38, f"total_cierres_general={metrics.total_cierres_general}, esperado 38"

    # === Seccion "Cierres por video y origen de pauta" (solo 1ra col, válidos) ===
    from src.analytics.closures_by_publication import (
        closures_by_publication,
        closures_by_origen_pauta,
    )
    tabla = closures_by_publication(df, 2026, 5)
    assert int(tabla["Cierres"].sum()) == 18, \
        f"tabla publicaciones total={tabla['Cierres'].sum()}, esperado 18"

    donut = closures_by_origen_pauta(df, 2026, 5)
    assert int(donut["Cierres"].sum()) == 18, \
        f"donut origen total={donut['Cierres'].sum()}, esperado 18"
