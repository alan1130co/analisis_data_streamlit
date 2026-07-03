"""Tests para el módulo de métricas."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.metrics import (
    compute_all_metrics,
    is_marketing,
    is_organico,
    is_tiktok,
    is_qualified_mask,
    is_asesor_comercial,
    is_cesar_augusto,
    _is_active_estado,
)

_ACTIVO = "activo"


@pytest.fixture
def sample_df():
    """DataFrame mínimo con casos cubiertos: con/sin propietario, distintos motivos, cierres."""
    return pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1), "propietario": "Sofia", "estado": _ACTIVO,
            "Motivo de no cierre": "cliente potencial",
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook", "Cantidad de cierres": 1,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 4, 10), "propietario": "Ana", "estado": "no se establecio contacto",
            "Motivo de no cierre": "no se logró contactar",
            "canal online": "inbox", "Canal offline": None,
            "Origen de la pauta": None, "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        {
            "creado": datetime(2026, 4, 15), "propietario": None, "estado": "en transito",
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


def test_asignados_solo_asesores_comerciales(sample_df):
    # Sofia y Ana son Asesores Comerciales; el 3er lead no tiene propietario.
    m = compute_all_metrics(sample_df, sample_df)
    assert m.asignados == 2


def test_asignados_excluye_cuentas_no_comerciales():
    """Cartera SM y Alan David Coneo Rodriguez no cuentan como Asignados."""
    _base = {
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        "Motivo de no cierre": None, "Cantidad de cierres": None, "estado": "en transito",
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "Sofia de la Hoz"},
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "Cartera SM"},
        {**_base, "creado": datetime(2026, 4, 3), "propietario": "Alan David Coneo Rodriguez"},
    ])
    m = compute_all_metrics(df, df)
    assert m.asignados == 1
    assert is_asesor_comercial("Cartera SM") is False
    assert is_asesor_comercial("Alan David Coneo Rodriguez") is False
    assert is_asesor_comercial("Sofia de la Hoz") is True


def test_calificados_se_calcula_sobre_asignados_no_sobre_creados():
    """Embudo estricto: Calificados es subconjunto de Asignados, no de Creados."""
    _base = {
        "canal online": "inbox", "Canal offline": None, "Origen de la pauta": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        "Cantidad de cierres": None, "estado": "en transito",
    }
    df = pd.DataFrame([
        # Asignado + calificado (motivo QUALIFIED)
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "Sofia",
         "Motivo de no cierre": "cliente potencial"},
        # Asignado + NO calificado (UNQUALIFIED)
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "Ana",
         "Motivo de no cierre": "no se logró contactar"},
        # Sin propietario → no es Asignado, no debe entrar al embudo
        {**_base, "creado": datetime(2026, 4, 3), "propietario": None,
         "Motivo de no cierre": None},
    ])
    m = compute_all_metrics(df, df)
    assert m.asignados == 2
    assert m.calificados == 1
    assert m.no_calificados == 1
    assert m.calificados + m.no_calificados == m.asignados


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


def test_motivo_cliente_de_seguimiento_es_calificado():
    row = pd.DataFrame([{
        "Motivo de no cierre": "Cliente de seguimiento", "Cantidad de cierres": None,
    }])
    assert is_qualified_mask(row).all()


def test_cierre_valido_requiere_estado_activo(sample_df):
    """Un cierre solo cuenta si el lead está Activo (o Activo - mora)."""
    m_activo = compute_all_metrics(sample_df, sample_df)
    assert m_activo.total_cierres == 1  # Sofia: pauta, activo, con cierre en abril

    df_inactivo = sample_df.copy()
    df_inactivo.loc[0, "estado"] = "inactivo"
    m_inactivo = compute_all_metrics(df_inactivo, df_inactivo)
    assert m_inactivo.total_cierres == 0

    df_mora = sample_df.copy()
    df_mora.loc[0, "estado"] = "activo - mora"
    m_mora = compute_all_metrics(df_mora, df_mora)
    assert m_mora.total_cierres == 1


def test_is_active_estado():
    assert _is_active_estado({"estado": "Activo"}) is True
    assert _is_active_estado({"estado": "activo - mora"}) is True
    assert _is_active_estado({"estado": "inactivo"}) is False
    assert _is_active_estado({"estado": "en transito"}) is False
    assert _is_active_estado({"estado": None}) is False


def test_total_cierres_solo_pauta_y_organico():
    """total_cierres = cierres válidos de Pauta + Orgánico; excluye TikTok y Referidos."""
    _base = {
        "propietario": "Sofia", "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
        "estado": _ACTIVO, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1),
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Fecha de cierre": datetime(2026, 4, 5)},
        {**_base, "creado": datetime(2026, 4, 2),
         "canal online": "inbox", "Canal offline": "orgánico",
         "Origen de la pauta": None, "Fecha de cierre": datetime(2026, 4, 6)},
        {**_base, "creado": datetime(2026, 4, 3),
         "canal online": "inbox", "Canal offline": "tiktok",
         "Origen de la pauta": None, "Fecha de cierre": datetime(2026, 4, 7)},
        {**_base, "creado": datetime(2026, 4, 4),
         "canal online": "inbox", "Canal offline": "referido externo",
         "Origen de la pauta": None, "Fecha de cierre": datetime(2026, 4, 8)},
    ])
    m = compute_all_metrics(df, df)
    assert m.total_cierres == 2  # solo pauta + orgánico
    assert m.total_cierres_general == 4  # las 4 fuentes


def test_cierres_marketing_suma_las_4_columnas():
    """cierres_marketing debe sumar 1er+2do+3er+4to cierre válidos del mes."""
    lead = {
        "creado": datetime(2026, 3, 1), "propietario": "Sofia", "estado": _ACTIVO,
        "Motivo de no cierre": None,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook", "Cantidad de cierres": 2,
        "Fecha de cierre": datetime(2026, 3, 5),
        "Fecha de segundo cierre": datetime(2026, 4, 10),
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    april_anchor = {
        "creado": datetime(2026, 4, 1), "propietario": "Ana", "estado": "en transito",
        "Motivo de no cierre": None,
        "canal online": "inbox", "Canal offline": None,
        "Origen de la pauta": None, "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df_full = pd.DataFrame([lead, april_anchor])
    df_period = pd.DataFrame([april_anchor])
    m = compute_all_metrics(df_period, df_full)
    assert m.cierres_marketing == 1  # el 2do cierre de marzo cae en abril


def test_cierres_marketing_y_referidos_separan_correctamente():
    """Un cierre de Facebook y otro de Referido (sin redes) en el mismo mes deben separarse."""
    facebook_lead = {
        "creado": datetime(2026, 4, 1), "propietario": "Sofia", "estado": _ACTIVO,
        "Motivo de no cierre": None,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook", "Cantidad de cierres": 1,
        "Fecha de cierre": datetime(2026, 4, 5),
        "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    referido_lead = {
        "creado": datetime(2026, 4, 10), "propietario": "Ana", "estado": _ACTIVO,
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
    assert m.total_cierres == 1  # solo pauta (el referido no cuenta en total_cierres)
    assert m.total_cierres_general == 2


def test_empty_df():
    m = compute_all_metrics(pd.DataFrame(), pd.DataFrame())
    assert m.creados == 0
    assert m.eficiencia_bruta == 0.0


# ---------------------------------------------------------------------------
# is_marketing / is_organico / is_tiktok
# ---------------------------------------------------------------------------

def test_is_marketing_referido_de_redes_es_referido_no_pauta():
    """Fix de fuga de referidos: 'Referido cliente activo - Redes' es Referido, no Pauta."""
    row = pd.Series({"Canal offline": "Referido cliente activo - Redes", "canal online": "inbox"})
    assert is_marketing(row) is False


def test_is_marketing_canal_offline_vacio_es_referido():
    """Canal offline vacío o None → siempre Referido, nunca Marketing."""
    row_empty = pd.Series({"Canal offline": "", "canal online": "paid social"})
    row_none = pd.Series({"Canal offline": None, "canal online": "paid social"})
    assert is_marketing(row_empty) is False
    assert is_marketing(row_none) is False


def test_is_marketing_otros_referidos_siguen_siendo_referido():
    casos = [
        {"Canal offline": "Referido externo"},
        {"Canal offline": "Referido propio"},
        {"Canal offline": "Referido cliente activo - Referido"},
        {"Canal offline": "Referido socio"},
        {"Canal offline": "Referido abogado"},
    ]
    for caso in casos:
        assert is_marketing(caso) is False, f"Falló: {caso}"


def test_is_marketing_canales_marketing_siguen_siendo_pauta():
    casos = [
        {"Canal offline": "Clientify - Whatsapp"},
        {"Canal offline": "Clientify - Facebook"},
        {"Canal offline": "Clientify - Instagram"},
        {"Canal offline": "Formulario de Facebook - Cliente Potencial"},
        {"Canal offline": "Formulario web"},
        {"Canal offline": "Llamada Entrante"},
    ]
    for caso in casos:
        assert is_marketing(caso) is True, f"Falló: {caso}"


def test_is_marketing_excluye_tiktok_y_organico():
    """TikTok y Orgánico ya NO son Pauta: son categorías propias."""
    assert is_marketing({"Canal offline": "Tiktok"}) is False
    assert is_marketing({"Canal offline": "Orgánico"}) is False
    assert is_marketing({"Canal offline": "organico"}) is False


def test_is_marketing_origen_pauta_prioritario_sobre_inbox_referral():
    """Click-to-Message: canal online=inbox-referral pero Origen de la pauta=Instagram → Pauta."""
    row = pd.Series({
        "Canal offline": "Clientify - Whatsapp",
        "canal online": "inbox-referral",
        "Origen de la pauta": "['Instagram']",
    })
    assert is_marketing(row) is True


def test_is_tiktok():
    assert is_tiktok({"Canal offline": "Tiktok", "Origen de la pauta": None}) is True
    assert is_tiktok({"Canal offline": "tik tok", "Origen de la pauta": None}) is True
    assert is_tiktok({"Canal offline": None, "Origen de la pauta": "TikTok"}) is True
    assert is_tiktok({"Canal offline": "Clientify - Facebook", "Origen de la pauta": None}) is False


def test_is_organico():
    assert is_organico({"Canal offline": "Orgánico", "Origen de la pauta": None}) is True
    assert is_organico({"Canal offline": "organico", "Origen de la pauta": None}) is True
    assert is_organico({"Canal offline": "Facebook", "Origen de la pauta": None}) is True
    assert is_organico({"Canal offline": "Messenger", "Origen de la pauta": None}) is True
    # TikTok tiene prioridad sobre Orgánico
    assert is_organico({"Canal offline": "Tiktok", "Origen de la pauta": None}) is False


def test_is_cesar_augusto():
    assert is_cesar_augusto({"propietario": "Cesar Augusto Perez Tafur"}) is True
    assert is_cesar_augusto({"propietario": "cesar augusto"}) is True
    assert is_cesar_augusto({"propietario": "Sofia de la Hoz"}) is False
    assert is_cesar_augusto({"propietario": None}) is False


# ---------------------------------------------------------------------------
# Leads Pauta / Orgánico / TikTok + filtro César Augusto
# ---------------------------------------------------------------------------

def _lead(canal_offline, propietario, estado="en transito", creado=datetime(2026, 4, 1), origen=None):
    return {
        "creado": creado, "propietario": propietario, "estado": estado,
        "canal online": None, "Canal offline": canal_offline, "Origen de la pauta": origen,
        "Motivo de no cierre": None, "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }


def test_leads_pauta_organico_tiktok_generales():
    df = pd.DataFrame([
        _lead("Clientify - Facebook", "sofia"),
        _lead("Orgánico", "ana"),
        _lead("Tiktok", "carlos"),
        _lead("Referido externo", "juan"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_pauta == 1
    assert m.leads_organico == 1
    assert m.leads_tiktok == 1


def test_cesar_augusto_messenger_instagram_suman_a_organico_tiktok_sin_importar_estado():
    """Suma 1 (César + Messenger/Instagram): cuenta siempre, sin importar el
    estado — 'representan comentarios de usuarios'. No se divide entre las
    tarjetas individuales de Orgánico/TikTok, solo en el total combinado."""
    df = pd.DataFrame([
        # César, Messenger, ACTIVO → sí cuenta (no hay filtro de estado)
        _lead("Messenger", "Cesar Augusto Perez Tafur", estado=_ACTIVO),
        # César, Instagram, en tránsito → sí cuenta
        _lead("Instagram", "Cesar Augusto Perez Tafur", estado="en transito"),
        # César, Facebook → NO cuenta (Suma 1 es solo Messenger/Instagram)
        _lead("Clientify - Facebook", "Cesar Augusto Perez Tafur", estado="en transito"),
        # César, TikTok literal → NO cuenta (fuera de Suma 1 y excluido de Suma 2)
        _lead("Tiktok", "Cesar Augusto Perez Tafur", estado="en transito"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico_tiktok == 2  # Messenger + Instagram, nada más
    assert m.leads_organico == 0  # Suma 1 no se reparte a la tarjeta individual
    assert m.leads_tiktok == 0


def test_leads_organico_tiktok_generales_no_incluyen_a_cesar():
    """Leads de Orgánico/TikTok de OTROS asesores (no César) se cuentan normal
    vía Suma 2, sin verse afectados por la regla especial de César."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia"),
        _lead("Tiktok", "ana"),
        _lead("Instagram", "Cesar Augusto Perez Tafur"),  # Suma 1, no Suma 2
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico == 1       # sofia
    assert m.leads_tiktok == 1         # ana
    assert m.leads_organico_tiktok == 3  # sofia + ana + césar (suma 1)


def test_leads_pauta_no_afectado_por_filtro_cesar():
    """El filtro de César Augusto solo aplica a Orgánico/TikTok, no a Pauta."""
    df = pd.DataFrame([
        _lead("Clientify - Facebook", "Cesar Augusto Perez Tafur", estado="en transito"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_pauta == 1


# ---------------------------------------------------------------------------
# Eficiencias
# ---------------------------------------------------------------------------

def test_eficiencia_pauta_calculo_correcto():
    """100 leads pauta asignados a Asesor Comercial, 5 con cierre válido en el mes."""
    leads = []
    for i in range(95):
        leads.append({
            "creado": datetime(2026, 4, 1), "propietario": "asesor", "estado": "en transito",
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook", "Motivo de no cierre": None,
            "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        })
    for i in range(5):
        leads.append({
            "creado": datetime(2026, 4, 1), "propietario": "asesor", "estado": _ACTIVO,
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook", "Motivo de no cierre": None,
            "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 15),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        })
    df = pd.DataFrame(leads)
    m = compute_all_metrics(df, df)
    assert m.leads_pauta == 100
    assert m.asignados_pauta == 100
    assert m.cierres_marketing == 5
    assert m.eficiencia_pauta == pytest.approx(5.0)  # (5*100)/100


def test_eficiencia_bruta_formula():
    """Eficiencia Bruta = Cierres(Pauta+Organico)*100 / (AsignadosPauta+Organico+TikTok+Calificados+NoCalificados)."""
    df = pd.DataFrame([
        # Pauta, asignado, calificado, con cierre válido
        {"creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": _ACTIVO,
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Orgánico
        {"creado": datetime(2026, 4, 2), "propietario": "ana", "estado": "en transito",
         "canal online": None, "Canal offline": "orgánico",
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    # asignados_pauta=1, leads_organico=1, leads_tiktok=0, calificados=2, no_calificados=0
    # denom = 1+1+0+2+0 = 4; numerador = total_cierres = 1
    assert m.eficiencia_bruta == pytest.approx(1 * 100 / 4)


# ---------------------------------------------------------------------------
# Tarjetas KPI
# ---------------------------------------------------------------------------

def test_get_kpi_definitions_todos_devuelve_8_tarjetas():
    """Layout original de 8 tarjetas (revertida la grilla de 10)."""
    from src.analytics.kpis import get_kpi_definitions
    assert len(get_kpi_definitions("Todos")) == 8


def test_kpi_todos_incluye_tarjetas_en_orden_original_con_organico_tiktok_unificado():
    """Orden: Creados, Leads Pauta, Leads Organico+TikTok (unificado), Calificados,
    No calificados, Total Cierres, % Eficiencia Pauta, % Eficiencia Global."""
    from src.analytics.kpis import KPI_DEFINITIONS_TODOS
    keys = [k.key for k in KPI_DEFINITIONS_TODOS]
    assert keys == [
        "creados", "leads_pauta", "leads_organico_tiktok",
        "calificados", "no_calificados", "total_cierres",
        "eficiencia_pauta", "eficiencia_global",
    ]


# ---------------------------------------------------------------------------
# Nuevos campos: asignados por canal, tarjeta combinada, cierres_no_pauta,
# eficiencia_global (fórmulas exactas pedidas para Soluciones Migratorias)
# ---------------------------------------------------------------------------

def test_leads_organico_tiktok_es_la_suma_de_ambos():
    df = pd.DataFrame([
        _lead("Orgánico", "sofia"),
        _lead("Tiktok", "ana"),
        _lead("Clientify - Facebook", "carlos"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico_tiktok == m.leads_organico + m.leads_tiktok == 2


def test_asignados_organico_y_tiktok_solo_cuentan_asesores_comerciales():
    df = pd.DataFrame([
        _lead("Orgánico", "sofia"),          # asignado a asesor comercial
        _lead("Tiktok", "cartera sm"),        # NO comercial → no debe contar
        _lead("Orgánico", None),              # sin propietario → no asignado
    ])
    m = compute_all_metrics(df, df)
    assert m.asignados_organico == 1
    assert m.asignados_tiktok == 0


def test_cierres_no_pauta_agrupa_organico_tiktok_y_referidos_sin_fuga():
    """cierres_no_pauta ('Referidos (R)' en la tarjeta) debe sumar Organico + TikTok +
    Referidos estrictos, de forma que Cierres Pauta (M) + Cierres Referidos (R) sea
    SIEMPRE igual a total_cierres_general (ninguna categoría se pierde)."""
    _base = {
        "propietario": "Sofia", "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
        "estado": _ACTIVO, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1),
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Fecha de cierre": datetime(2026, 4, 5)},
        {**_base, "creado": datetime(2026, 4, 2),
         "canal online": "inbox", "Canal offline": "orgánico",
         "Origen de la pauta": None, "Fecha de cierre": datetime(2026, 4, 6)},
        {**_base, "creado": datetime(2026, 4, 3),
         "canal online": "inbox", "Canal offline": "tiktok",
         "Origen de la pauta": None, "Fecha de cierre": datetime(2026, 4, 7)},
        {**_base, "creado": datetime(2026, 4, 4),
         "canal online": "inbox", "Canal offline": "referido externo",
         "Origen de la pauta": None, "Fecha de cierre": datetime(2026, 4, 8)},
    ])
    m = compute_all_metrics(df, df)
    assert m.cierres_no_pauta == 3  # organico + tiktok + referido
    assert m.cierres_marketing + m.cierres_no_pauta == m.total_cierres_general == 4


def test_eficiencia_pauta_usa_total_asignados_no_solo_asignados_pauta():
    """% Eficiencia de Pauta = (Cierres por Pauta * 100) / Total Asignado a los
    Asesores (universo completo, no solo el subconjunto de pauta) — para que
    no dé un porcentaje inflado cuando hay leads de otros canales."""
    df = pd.DataFrame([
        # Pauta, asignada, 1 cierre válido
        {"creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": _ACTIVO,
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido, asignado (NO es pauta) — antes no entraba en el denominador
        {"creado": datetime(2026, 4, 2), "propietario": "ana", "estado": "en transito",
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    assert m.asignados == 2
    assert m.asignados_pauta == 1
    assert m.cierres_marketing == 1
    # Con la fórmula vieja (asignados_pauta=1) daría 100%; con la nueva (asignados=2) da 50%.
    assert m.eficiencia_pauta == pytest.approx(1 * 100 / 2)


def test_eficiencia_global_usa_total_cierres_general_y_asignados_totales():
    """% Eficiencia Global = (Total Cierres de TODA la operación * 100) /
    Total Asignado a los Asesores — debe reflejar también los cierres de
    Referidos (antes la fórmula los ignoraba por completo en el numerador,
    dando 0% pese a haber cierres reales)."""
    df = pd.DataFrame([
        # Pauta, asignada, SIN cierre
        {"creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": "en transito",
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido, asignado, CON cierre válido
        {"creado": datetime(2026, 4, 2), "propietario": "ana", "estado": _ACTIVO,
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 10),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    assert m.asignados == 2
    assert m.total_cierres_general == 1  # el cierre de Referidos
    assert m.total_cierres == 0          # el KPI legado (solo pauta+organico) lo ignora
    # Con la fórmula vieja (numerador solo pauta+organico+tiktok=0) daría 0% pese
    # al cierre real de Referidos; la nueva sí lo refleja: 1*100/2 = 50%.
    assert m.eficiencia_global == pytest.approx(1 * 100 / 2)


def test_eficiencia_pauta_y_global_ya_vienen_en_puntos_porcentuales():
    """eficiencia_pauta/eficiencia_global se muestran con format_percent_raw (sin
    re-multiplicar por 100) porque la fórmula del negocio ya incluye el *100."""
    from src.utils.formatters import format_percent_raw
    assert format_percent_raw(5.0) == "5.0%"
