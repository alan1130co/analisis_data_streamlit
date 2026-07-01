"""Tests para el módulo de métricas."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.metrics import compute_all_metrics, is_marketing, is_qualified_mask


@pytest.fixture
def sample_df():
    """DataFrame mínimo con casos cubiertos: con/sin propietario, distintos motivos, cierres."""
    return pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1), "propietario": "Sofia",
            "Motivo de no cierre": "cliente potencial",
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook", "Cantidad de cierres": 1,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 4, 10), "propietario": "Ana",
            "Motivo de no cierre": "no se logró contactar",
            "canal online": "inbox", "Canal offline": None,
            "Origen de la pauta": None, "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 4, 15), "propietario": None,
            "Motivo de no cierre": "su caso no aplicaba",
            "canal online": "paid social", "Canal offline": "clientify - instagram",
            "Origen de la pauta": "instagram", "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])


def test_creados(sample_df):
    m = compute_all_metrics(sample_df, sample_df)
    assert m.creados == 3


def test_asignados(sample_df):
    m = compute_all_metrics(sample_df, sample_df)
    assert m.asignados == 2  # Sofia y Ana


def test_calificados():
    """Las 3 condiciones de calificación: motivo calificado, motivo vacío, cierre >= 1."""
    _base = {
        "canal online": "inbox", "Canal offline": None,
        "Origen de la pauta": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "Sofia",
         "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": None},
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "Ana",
         "Motivo de no cierre": "no se logró contactar", "Cantidad de cierres": None},
        {**_base, "creado": datetime(2026, 4, 3), "propietario": "Carlos",
         "Motivo de no cierre": None, "Cantidad de cierres": None},
    ])
    # Row 0: QUALIFIED_MOTIVES → calificado
    # Row 1: UNQUALIFIED_MOTIVES, sin cierre → NO calificado
    # Row 2: motivo vacío/None → calificado (aún sin clasificar)
    m = compute_all_metrics(df, df)
    assert m.calificados == 2


def test_calificados_motivo_vacio_cuenta_como_calificado():
    """Motivo None/vacío es calificado porque el lead aún no fue clasificado."""
    _base = {
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "Sofia",
         "Motivo de no cierre": None, "Cantidad de cierres": None},
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "Ana",
         "Motivo de no cierre": "", "Cantidad de cierres": None},
    ])
    mask = is_qualified_mask(df)
    assert mask.all(), "Motivos vacíos/None deben ser calificados"


def test_calificados_motivo_unqualified_no_cuenta_como_calificado():
    """Motivo explícito en UNQUALIFIED_MOTIVES sin cierre → NO calificado."""
    _base = {
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "Sofia",
         "Motivo de no cierre": "no se logró contactar", "Cantidad de cierres": None},
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "Ana",
         "Motivo de no cierre": "su caso no aplicaba", "Cantidad de cierres": None},
    ])
    mask = is_qualified_mask(df)
    assert not mask.any(), "Motivos en UNQUALIFIED_MOTIVES sin cierre no deben ser calificados"


def test_total_cierres(sample_df):
    m = compute_all_metrics(sample_df, sample_df)
    assert m.total_cierres == 1
    assert m.cierres_1 == 1
    assert m.cierres_2 == 0


def test_eficiencia_total(sample_df):
    # sample_df: calificados=1 (solo Sofia, que tiene cierre), total_cierres=1
    # eficiencia_total = total_cierres / calificados = 1/1
    m = compute_all_metrics(sample_df, sample_df)
    assert m.eficiencia_total == pytest.approx(1.0)


def test_leads_redes(sample_df):
    # Row 0 y Row 2 tienen canal online="paid social"
    m = compute_all_metrics(sample_df, sample_df)
    assert m.leads_redes == 2


def test_empty_df():
    m = compute_all_metrics(pd.DataFrame(), pd.DataFrame())
    assert m.creados == 0
    assert m.eficiencia_total == 0.0


def test_cross_month_closure_por_pautas():
    """Lead creado en marzo con Fecha de segundo cierre en abril debe contar
    en cierres_por_pautas de abril cuando se analiza ese mes."""
    march_lead = {
        "creado": datetime(2026, 3, 15), "propietario": "Sofia",
        "Motivo de no cierre": "cliente potencial",
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook", "Cantidad de cierres": 2,
        "Fecha de cierre": datetime(2026, 3, 20),
        "Fecha de segundo cierre": datetime(2026, 4, 10),
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    # df_period = leads creados en abril (solo uno orgánico, sin cierre, para fijar año/mes)
    april_anchor = {
        "creado": datetime(2026, 4, 1), "propietario": "Ana",
        "Motivo de no cierre": None,
        "canal online": "inbox", "Canal offline": None,
        "Origen de la pauta": None, "Cantidad de cierres": 0,
        "Fecha de cierre": pd.NaT,
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    df_full = pd.DataFrame([march_lead, april_anchor])
    df_period = pd.DataFrame([april_anchor])

    m = compute_all_metrics(df_period, df_full)
    # El lead de marzo tiene Fecha de segundo cierre en abril y viene de pauta paga
    assert m.cierres_por_pautas == 1


def test_cierres_marketing_y_referidos_separan_correctamente():
    """Un cierre de Facebook y otro de Referido (sin redes) en el mismo mes deben separarse."""
    facebook_lead = {
        "creado": datetime(2026, 4, 1), "propietario": "Sofia",
        "Motivo de no cierre": None,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook", "Cantidad de cierres": 1,
        "Fecha de cierre": datetime(2026, 4, 5),
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    referido_lead = {
        "creado": datetime(2026, 4, 10), "propietario": "Ana",
        "Motivo de no cierre": None,
        "canal online": "inbox", "Canal offline": "referido externo",
        "Origen de la pauta": None, "Cantidad de cierres": 1,
        "Fecha de cierre": datetime(2026, 4, 15),
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([facebook_lead, referido_lead])
    m = compute_all_metrics(df, df)
    assert m.cierres_marketing == 1
    assert m.cierres_referidos == 1
    assert m.total_cierres == 2


def test_is_marketing_distingue_equipos():
    """'Clientify - Facebook' es Marketing; 'Referido externo' es Referidos; 'Referido cliente activo - Redes' es Marketing."""
    row_marketing = pd.Series({
        "Canal offline": "Clientify - Facebook",
        "canal online": "paid social",
    })
    row_referido = pd.Series({
        "Canal offline": "Referido externo",
        "canal online": "inbox",
    })
    row_redes = pd.Series({
        "Canal offline": "Referido cliente activo - Redes",
        "canal online": "inbox",
    })
    assert is_marketing(row_marketing) is True
    assert is_marketing(row_referido) is False
    assert is_marketing(row_redes) is True  # "redes" → PAUTA, no importa el prefijo


def test_is_marketing_canal_offline_vacio_es_referido():
    """Canal offline vacío o None → siempre Referido, nunca Marketing."""
    row_empty = pd.Series({"Canal offline": "", "canal online": "paid social"})
    row_none = pd.Series({"Canal offline": None, "canal online": "paid social"})
    assert is_marketing(row_empty) is False
    assert is_marketing(row_none) is False


def test_no_calificados_es_complemento_de_calificados():
    """calificados + no_calificados debe ser igual al total de leads del período."""
    _base = {
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "Sofia",
         "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": None},
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "Ana",
         "Motivo de no cierre": "no se logró contactar", "Cantidad de cierres": None},
        {**_base, "creado": datetime(2026, 4, 3), "propietario": "Carlos",
         "Motivo de no cierre": None, "Cantidad de cierres": None},
    ])
    m = compute_all_metrics(df, df)
    assert m.calificados + m.no_calificados == m.creados, (
        f"calificados={m.calificados} + no_calificados={m.no_calificados} != creados={m.creados}"
    )


def test_creados_pauta_mas_creados_referido_igual_creados():
    """creados_pauta + creados_referido debe ser igual al total de leads creados en el período."""
    leads = [
        # Marketing
        {"creado": datetime(2026, 4, 1), "propietario": "sofia",
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido
        {"creado": datetime(2026, 4, 2), "propietario": "ana",
         "canal online": "inbox", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido (sin canal offline)
        {"creado": datetime(2026, 4, 3), "propietario": None,
         "canal online": "inbox", "Canal offline": None,
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ]
    df = pd.DataFrame(leads)
    m = compute_all_metrics(df, df)
    assert m.creados_pauta + m.creados_referido == m.creados, (
        f"creados_pauta={m.creados_pauta} + creados_referido={m.creados_referido} != creados={m.creados}"
    )


def test_cierres_adicionales_suma_2_3_4():
    """Un lead con 1er y 2do cierre en abril: total_cierres=1 (solo 1ra col), adicionales=1."""
    lead = {
        "creado": datetime(2026, 4, 1), "propietario": "Sofia",
        "Motivo de no cierre": None,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook", "Cantidad de cierres": 2,
        "Fecha de cierre": datetime(2026, 4, 5),
        "Fecha de segundo cierre": datetime(2026, 4, 20),
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([lead])
    m = compute_all_metrics(df, df)
    assert m.cierres_1 == 1
    assert m.cierres_adicionales == 1
    assert m.total_cierres == 1  # solo 1ra columna, igual al filtro de Clientify


def test_is_marketing_organico_es_pauta():
    """Regla de negocio: canal 'Orgánico' cuenta como Pauta (no como Referido)."""
    casos = [
        {"Canal offline": "Orgánico", "canal online": ""},
        {"Canal offline": "orgánico", "canal online": ""},
        {"Canal offline": "ORGANICO", "canal online": ""},
        {"Canal offline": "organico", "canal online": ""},
    ]
    for caso in casos:
        assert is_marketing(caso) is True, f"Falló: {caso}"


# ---------------------------------------------------------------------------
# Tests PASO 2: regla "redes"
# ---------------------------------------------------------------------------

def test_is_marketing_canal_con_redes_es_pauta():
    """Cualquier canal que contenga 'Redes' cae en PAUTA, sin importar el prefijo."""
    casos = [
        {"Canal offline": "Referido cliente activo - Redes"},
        {"Canal offline": "Pauta - Redes"},
        {"Canal offline": "redes sociales"},
        {"Canal offline": "Cliente vino por redes"},
    ]
    for caso in casos:
        assert is_marketing(caso) is True, f"Falló: {caso}"


def test_is_marketing_otros_referidos_siguen_siendo_referido():
    """Referidos que NO contienen 'Redes' siguen siendo REFERIDO."""
    casos = [
        {"Canal offline": "Referido externo"},
        {"Canal offline": "Referido propio"},
        {"Canal offline": "Referido cliente activo - Referido"},
        {"Canal offline": "Referido socio"},
        {"Canal offline": "Referido abogado"},
    ]
    for caso in casos:
        assert is_marketing(caso) is False, f"Falló: {caso}"


def test_is_marketing_canales_marketing_sin_redes_siguen_siendo_pauta():
    """Canales tradicionales de marketing sin 'Redes' siguen siendo PAUTA."""
    casos = [
        {"Canal offline": "Clientify - Whatsapp"},
        {"Canal offline": "Clientify - Facebook"},
        {"Canal offline": "Clientify - Instagram"},
        {"Canal offline": "Formulario de Facebook - Cliente Potencial"},
        {"Canal offline": "Formulario web"},
        {"Canal offline": "Llamada Entrante"},
        {"Canal offline": "Tiktok"},
    ]
    for caso in casos:
        assert is_marketing(caso) is True, f"Falló: {caso}"


# ---------------------------------------------------------------------------
# Tests CAMBIO 5: campos desagregados por equipo
# ---------------------------------------------------------------------------

_BASE_MKT = {
    "canal online": "paid social", "Canal offline": "clientify - facebook",
    "Origen de la pauta": "facebook", "Motivo de no cierre": None,
    "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
    "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
}
_BASE_REF = {
    "canal online": "inbox", "Canal offline": "referido externo",
    "Origen de la pauta": None, "Motivo de no cierre": None,
    "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
    "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
}


def _mixed_metrics():
    """2 leads marketing (1 calificado, 1 no), 1 lead referido calificado."""
    df = pd.DataFrame([
        {**_BASE_MKT, "creado": datetime(2026, 4, 1), "propietario": "Sofia",
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5)},
        {**_BASE_MKT, "creado": datetime(2026, 4, 2), "propietario": "Ana",
         "Motivo de no cierre": "no se logró contactar"},
        {**_BASE_REF, "creado": datetime(2026, 4, 3), "propietario": "Carlos"},
    ])
    return compute_all_metrics(df, df)


def test_calificados_pauta_mas_referido_igual_total():
    m = _mixed_metrics()
    assert m.calificados_pauta + m.calificados_referido == m.calificados


def test_creados_pauta_mas_referido_igual_creados():
    m = _mixed_metrics()
    assert m.creados_pauta + m.creados_referido == m.creados


def test_no_calificados_pauta_mas_referido_igual_total():
    m = _mixed_metrics()
    assert m.no_calificados_pauta + m.no_calificados_referido == m.no_calificados


def test_eficiencia_pauta_calculo_correcto():
    """100 leads pauta, 5 con cierre en el mes → eficiencia_pauta = 0.05."""
    leads = [{**_BASE_MKT, "creado": datetime(2026, 4, 1), "propietario": "asesor"}
             for _ in range(95)]
    for _ in range(5):
        leads.append({
            **_BASE_MKT, "creado": datetime(2026, 4, 1), "propietario": "asesor",
            "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 15),
        })
    df = pd.DataFrame(leads)
    m = compute_all_metrics(df, df)
    assert m.creados_pauta == 100
    assert m.cierres_marketing == 5
    assert m.eficiencia_pauta == pytest.approx(0.05)


def test_eficiencia_referido_calculo_correcto():
    """100 leads referido, 5 con cierre en el mes → eficiencia_referido = 0.05."""
    leads = [{**_BASE_REF, "creado": datetime(2026, 4, 1), "propietario": "asesor"}
             for _ in range(95)]
    for _ in range(5):
        leads.append({
            **_BASE_REF, "creado": datetime(2026, 4, 1), "propietario": "asesor",
            "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 15),
        })
    df = pd.DataFrame(leads)
    m = compute_all_metrics(df, df)
    assert m.creados_referido == 100
    assert m.cierres_referidos == 5
    assert m.eficiencia_referido == pytest.approx(0.05)


def test_get_kpi_definitions_marketing_devuelve_8_tarjetas():
    from src.analytics.kpis import get_kpi_definitions
    assert len(get_kpi_definitions("Marketing (pautas)")) == 8


def test_get_kpi_definitions_referidos_devuelve_8_tarjetas():
    from src.analytics.kpis import get_kpi_definitions
    assert len(get_kpi_definitions("Referidos")) == 8


def test_get_kpi_definitions_todos_devuelve_8_tarjetas():
    from src.analytics.kpis import get_kpi_definitions
    assert len(get_kpi_definitions("Todos")) == 8


def test_kpi_marketing_usa_adicionales_pauta_no_total():
    from src.analytics.kpis import KPI_DEFINITIONS_MARKETING
    keys = [k.key for k in KPI_DEFINITIONS_MARKETING]
    assert "cierres_adicionales_pauta" in keys
    assert "cierres_adicionales" not in keys


def test_kpi_referidos_usa_adicionales_referido_no_total():
    from src.analytics.kpis import KPI_DEFINITIONS_REFERIDOS
    keys = [k.key for k in KPI_DEFINITIONS_REFERIDOS]
    assert "cierres_adicionales_referido" in keys
    assert "cierres_adicionales" not in keys


def test_kpi_todos_si_usa_adicionales_total():
    from src.analytics.kpis import KPI_DEFINITIONS_TODOS
    keys = [k.key for k in KPI_DEFINITIONS_TODOS]
    assert "cierres_adicionales" in keys


def test_eficiencia_total_usa_calificados_no_creados():
    """Con 4 calificados y 1 cierre → eficiencia_total = 0.25, no 1/creados."""
    _base = {
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
        "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "A",
         "Motivo de no cierre": "", "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5)},
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "B", "Motivo de no cierre": ""},
        {**_base, "creado": datetime(2026, 4, 3), "propietario": "C", "Motivo de no cierre": ""},
        {**_base, "creado": datetime(2026, 4, 4), "propietario": "D", "Motivo de no cierre": ""},
    ])
    m = compute_all_metrics(df, df)
    assert m.calificados == 4
    assert m.total_cierres == 1
    assert m.eficiencia_total == pytest.approx(0.25)


def test_kpi_todos_no_tiene_eficiencias_individuales():
    """KPI_DEFINITIONS_TODOS no debe incluir eficiencia_pauta ni eficiencia_referido."""
    from src.analytics.kpis import KPI_DEFINITIONS_TODOS
    keys = {k.key for k in KPI_DEFINITIONS_TODOS}
    assert "eficiencia_pauta" not in keys
    assert "eficiencia_referido" not in keys
    assert "eficiencia_total" in keys
