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
    _is_valid_closure_estado,
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
    """Regla 2026-09-08: 'Creados del mes' solo cuenta Pauta u Orgánico
    (excluye Referido puro y cualquier lead sin canal identificable). En
    `sample_df`: fila 0 (Clientify - Facebook) y fila 2 (Clientify -
    Instagram) son Pauta → cuentan; fila 1 (Canal offline vacío, canal
    online 'inbox', sin Origen de la pauta) no es Pauta ni Orgánico → no
    cuenta. creados == 2, no 3."""
    m = compute_all_metrics(sample_df, sample_df)
    assert m.creados == 2


def test_creados_excluye_a_cesar_augusto(sample_df):
    """Regla 2026-09-03: 'Creados del mes' excluye a César Augusto (volumen
    atípico de comentarios/ruido en redes, no leads comerciales reales).
    Regla 2026-09-08: además solo cuenta Pauta/Orgánico (ver test_creados) —
    la base de sample_df ya da creados == 2 (no 3). El lead de César
    ('Orgánico', que SÍ sería Pauta/Orgánico) queda excluido igual por
    ~cesar_mask, así que sumarlo no cambia el conteo: sigue en 2.
    'Leads Orgánicos y TikTok' NO cambió: sigue sumando a César completo
    (esa tarjeta se confirmó explícitamente sin tocar)."""
    cesar_lead = {
        "creado": datetime(2026, 4, 20), "propietario": "Cesar Augusto Perez Tafur",
        "estado": "en transito", "Motivo de no cierre": None,
        "canal online": None, "Canal offline": "Orgánico", "Origen de la pauta": None,
        "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
        "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.concat([sample_df, pd.DataFrame([cesar_lead])], ignore_index=True)
    m = compute_all_metrics(df, df)
    assert m.creados == 2
    assert m.leads_organico_tiktok == 1


def test_creados_excluye_referido_puro():
    """Regla 2026-09-08: un lead Referido puro (Canal offline empieza con
    'referido', sin 'redes') no cuenta para 'Creados del mes', aunque no sea
    de César y esté perfectamente calificado."""
    df = pd.DataFrame([
        {"creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": _ACTIVO,
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"creado": datetime(2026, 4, 2), "propietario": "carlos", "estado": _ACTIVO,
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 6),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    assert m.creados == 1


def test_leads_clientify_whatsapp_y_formulario_facebook_cp_cuentan_por_etiquetas():
    """2026-09-08: reemplaza el match exacto contra 'Canal offline' (regla
    2026-09-04) por un substring sobre la columna 'Etiquetas' — confirmado
    directamente en Clientify: la línea '305-508-5147' identifica Clientify
    Whatsapp y '305-610-0002' identifica Formulario Facebook-CP. 'Etiquetas'
    es texto libre (lista de tags separados por coma), así que basta con que
    contenga la línea en cualquier parte, no un valor exacto."""
    df = pd.DataFrame([
        _lead("clientify - whatsapp", "sofia", etiquetas="whatsapp, 305-508-5147, vip"),
        _lead("clientify - whatsapp", "ana", etiquetas="305-508-5147"),
        _lead("formulario de facebook - cliente potencial", "carlos", etiquetas="fb-cp, 305-610-0002"),
        # Canal offline de Pauta pero SIN ninguna de las 2 líneas en Etiquetas
        # — no debe sumar a ninguna tarjeta (la clasificación ya no depende
        # de Canal offline en absoluto).
        _lead("clientify - facebook", "diana", etiquetas="otra etiqueta cualquiera"),
        # Etiquetas vacía/None — no debe sumar a ninguna tarjeta.
        _lead("clientify - whatsapp", "juan", etiquetas=None),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_clientify_whatsapp == 2
    assert m.leads_formulario_facebook_cp == 1


def test_leads_clientify_whatsapp_y_formulario_facebook_cp_ambas_lineas_a_la_vez():
    """Caso especial confirmado por el usuario: 129 leads reales tienen AMBAS
    líneas etiquetadas a la vez (contacto real por los 2 canales, no error de
    datos). Deben contar en LAS 2 tarjetas simultáneamente — las 2 máscaras
    son independientes (`.str.contains`), no hay elif/exclusión mutua."""
    df = pd.DataFrame([
        _lead("clientify - whatsapp", "sofia", etiquetas="305-508-5147, 305-610-0002"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_clientify_whatsapp == 1
    assert m.leads_formulario_facebook_cp == 1


def test_leads_clientify_whatsapp_y_formulario_facebook_cp_excluyen_a_cesar():
    """Mismo criterio que 'Creados del mes': un lead de César Augusto con la
    línea '305-508-5147' en 'Etiquetas' no debe sumar a la tarjeta."""
    df = pd.DataFrame([
        _lead("clientify - whatsapp", "Cesar Augusto Perez Tafur", etiquetas="305-508-5147"),
        _lead("clientify - whatsapp", "sofia", etiquetas="305-508-5147"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_clientify_whatsapp == 1


def test_creados_incluye_leads_solo_identificables_por_etiquetas():
    """Regla 2026-09-08c: `is_marketing()`/`is_organico()` dependen
    EXCLUSIVAMENTE de 'Canal offline'/'Origen de la pauta' — confirmado con
    datos reales (Agosto 2026) que 'Canal offline' viene vacío en 99.2% de
    los leads, así que 'creados' perdía casi todos los leads de Pauta
    identificables solo por la línea de WhatsApp/Formulario Facebook-CP en
    'Etiquetas' (634 leads reales en ese período). Un lead con 'Canal
    offline'/'Origen de la pauta' vacíos pero con esa línea en 'Etiquetas'
    ahora SÍ cuenta para 'creados', aunque is_marketing()/is_organico() lo
    descarten (verificado explícitamente acá: ambos dan False)."""
    df = pd.DataFrame([
        _lead(None, "sofia", origen=None, etiquetas="305-508-5147"),
    ])
    row = df.iloc[0]
    assert is_marketing(row) is False
    assert is_organico(row) is False

    m = compute_all_metrics(df, df)
    assert m.creados == 1


def test_creados_no_duplica_lead_con_ambas_lineas_de_etiquetas():
    """Un lead con AMBAS líneas de Etiquetas (WhatsApp + Formulario
    Facebook-CP) cuenta 1 SOLA vez en 'creados' — el `|` de pandas ya
    deduplica — aunque sume en las 2 tarjetas separadas de arriba."""
    df = pd.DataFrame([
        _lead(None, "sofia", origen=None, etiquetas="305-508-5147, 305-610-0002"),
    ])
    m = compute_all_metrics(df, df)
    assert m.creados == 1
    assert m.leads_clientify_whatsapp == 1
    assert m.leads_formulario_facebook_cp == 1


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


def test_calificados_motivo_vacio_no_cuenta_como_calificado():
    """Regla estricta (2026-08-12c): motivo vacío/None sin cierre real ya NO
    es calificado — antes contaba por defecto como 'aún sin clasificar'."""
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
    assert not mask.any(), "Motivos vacíos/None sin cierre real NO deben ser calificados"


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


def test_cierre_valido_excluye_solo_estado_inactivo(sample_df):
    """Regla de Cierre Válido (2026-07-03): un cierre cuenta salvo que 'estado'
    sea EXACTAMENTE 'inactivo'. Ya no se exige una lista blanca (activo/activo
    - mora): cualquier otro estado con fecha de cierre en el mes es válido."""
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

    # Estado intermedio (ni "activo" ni "inactivo"): con la regla vieja NO
    # contaba (lista blanca); con la nueva SÍ cuenta (solo se excluye "inactivo").
    df_intermedio = sample_df.copy()
    df_intermedio.loc[0, "estado"] = "en proceso de firma"
    m_intermedio = compute_all_metrics(df_intermedio, df_intermedio)
    assert m_intermedio.total_cierres == 1


def test_is_valid_closure_estado():
    assert _is_valid_closure_estado({"estado": "Activo"}) is True
    assert _is_valid_closure_estado({"estado": "activo - mora"}) is True
    assert _is_valid_closure_estado({"estado": "en transito"}) is True
    assert _is_valid_closure_estado({"estado": None}) is True
    assert _is_valid_closure_estado({"estado": "inactivo"}) is False
    assert _is_valid_closure_estado({"estado": "Inactivo"}) is False
    assert _is_valid_closure_estado({"estado": "  INACTIVO  "}) is False


def test_total_cierres_es_pauta_incluyendo_tiktok_y_organico():
    """2026-07-03e: total_cierres = cierres_marketing, que ahora INCLUYE
    TikTok y Orgánico (son Pauta); excluye solo Referido puro."""
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
    assert m.total_cierres == 3  # facebook + orgánico + tiktok (los 3 son Pauta ahora)
    assert m.total_cierres_general == 4  # Pauta(3) + Referido puro(1)


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

def test_is_marketing_referido_de_redes_es_pauta():
    """Regla 2026-07-03e (reemplaza el fix de fuga anterior): 'Referido cliente
    activo - Redes' es Pauta, no Referido — 'redes' en el nombre manda, aunque
    diga 'referido'. El check de 'redes' se evalúa ANTES que el de referido puro."""
    row = pd.Series({"Canal offline": "Referido cliente activo - Redes", "canal online": "inbox"})
    assert is_marketing(row) is True


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


def test_is_marketing_incluye_tiktok_y_organico():
    """Regla 2026-07-03e: TikTok y Orgánico ahora SÍ son Pauta."""
    assert is_marketing({"Canal offline": "Tiktok"}) is True
    assert is_marketing({"Canal offline": "Orgánico"}) is True
    assert is_marketing({"Canal offline": "organico"}) is True


def test_is_marketing_redes_sociales_explicitas_son_pauta():
    """'Cualquier canal de redes sociales' (Facebook/Instagram/WhatsApp/
    Messenger/etc.) es Pauta, incluso sin el prefijo 'Clientify - '."""
    assert is_marketing({"Canal offline": "Facebook"}) is True
    assert is_marketing({"Canal offline": "Instagram"}) is True
    assert is_marketing({"Canal offline": "WhatsApp"}) is True
    assert is_marketing({"Canal offline": "Messenger"}) is True


def test_is_marketing_check_de_redes_antes_que_referido():
    """El check de 'redes' se evalúa ANTES que el de 'referido puro' — por
    eso cualquier variante de 'referido...redes' es Pauta."""
    casos_pauta = [
        {"Canal offline": "Referido cliente activo - Redes"},
        {"Canal offline": "Referido de redes"},
        {"Canal offline": "Redes - referido"},
    ]
    for caso in casos_pauta:
        assert is_marketing(caso) is True, f"Falló (debería ser Pauta): {caso}"


def test_is_marketing_cualquier_variante_de_llamada_es_pauta():
    """2026-07-03f: cualquier Canal offline que contenga 'llamada' (Llamada
    Entrante, Llamada Telefónica, Llamada Saliente, etc.) es Pauta, por
    substring — no solo la igualdad exacta contra 'llamada entrante'."""
    casos_pauta = [
        {"Canal offline": "Llamada Entrante"},
        {"Canal offline": "Llamada Telefónica"},
        {"Canal offline": "Llamada Saliente"},
        {"Canal offline": "llamada"},
    ]
    for caso in casos_pauta:
        assert is_marketing(caso) is True, f"Falló (debería ser Pauta): {caso}"


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
    # TikTok tiene prioridad sobre Orgánico
    assert is_organico({"Canal offline": "Tiktok", "Origen de la pauta": None}) is False


def test_is_organico_no_incluye_facebook_messenger_instagram_para_poblacion_general():
    """Fix de la bolsa Orgánico/TikTok (2026-07-03): 'Facebook'/'Messenger'/
    'Instagram' en Canal offline YA NO cuentan como Orgánico para cualquier
    asesor — antes cualquier lead con esos canales se sumaba de más a la
    bolsa. Messenger/Instagram solo cuentan si además es César Augusto
    (ver is_cesar_comentario); Facebook cae en Pauta/Referido según el resto
    de columnas, no en Orgánico."""
    assert is_organico({"Canal offline": "Facebook", "Origen de la pauta": None}) is False
    assert is_organico({"Canal offline": "Messenger", "Origen de la pauta": None}) is False
    assert is_organico({"Canal offline": "Instagram", "Origen de la pauta": None}) is False


def test_is_cesar_augusto():
    assert is_cesar_augusto({"propietario": "Cesar Augusto Perez Tafur"}) is True
    assert is_cesar_augusto({"propietario": "cesar augusto"}) is True
    assert is_cesar_augusto({"propietario": "Sofia de la Hoz"}) is False
    assert is_cesar_augusto({"propietario": None}) is False


# ---------------------------------------------------------------------------
# Leads Pauta / Orgánico / TikTok + filtro César Augusto
# ---------------------------------------------------------------------------

def _lead(canal_offline, propietario, estado="en transito", creado=datetime(2026, 4, 1), origen=None,
          motivo="cliente potencial", etiquetas=None):
    """`motivo` por defecto viene diligenciado ("cliente potencial") para que
    los tests de clasificación por canal (Pauta/Orgánico/TikTok/César) no se
    vean afectados por la regla de "motivo diligenciado" de
    `leads_organico`/`leads_tiktok` (ver `has_motivo_diligenciado_mask`) a
    menos que la prueba pase `motivo=None` explícitamente para ese caso.

    `etiquetas`: valor crudo de la columna "Etiquetas" (2026-09-08, usada por
    leads_clientify_whatsapp/leads_formulario_facebook_cp) — None por
    defecto para no afectar tests que no la necesitan."""
    return {
        "creado": creado, "propietario": propietario, "estado": estado,
        "canal online": None, "Canal offline": canal_offline, "Origen de la pauta": origen,
        "Motivo de no cierre": motivo, "Cantidad de cierres": None,
        "Fecha de cierre": pd.NaT, "Fecha de segundo cierre": pd.NaT,
        "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        "Etiquetas": etiquetas,
    }


def test_leads_pauta_organico_tiktok_generales():
    """leads_pauta ahora incluye TikTok/Orgánico (regla 2026-07-03e); las
    tarjetas leads_organico/leads_tiktok (independientes de is_marketing)
    no cambian."""
    df = pd.DataFrame([
        _lead("Clientify - Facebook", "sofia"),
        _lead("Orgánico", "ana"),
        _lead("Tiktok", "carlos"),
        _lead("Referido externo", "juan"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_pauta == 3  # facebook + orgánico + tiktok
    assert m.leads_organico == 1
    assert m.leads_tiktok == 1


def test_cesar_augusto_cuenta_completo_sin_importar_canal_ni_estado():
    """Regla 2026-07-03h: Suma 1 = TODO lead de César Augusto, sin importar
    canal/origen de contacto ni estado. Reemplaza la regla anterior
    (solo Messenger/Instagram) que dejaba afuera leads reales de César con
    otros canales (p.ej. 'orgánico', 'inbox_whatsapp', vacío)."""
    df = pd.DataFrame([
        _lead("Messenger", "Cesar Augusto Perez Tafur", estado=_ACTIVO),
        _lead("Instagram", "Cesar Augusto Perez Tafur", estado="en transito"),
        # Antes NO contaban (fuera de Messenger/Instagram) — ahora SÍ cuentan.
        _lead("Clientify - Facebook", "Cesar Augusto Perez Tafur", estado="en transito"),
        _lead("Tiktok", "Cesar Augusto Perez Tafur", estado="en transito"),
        _lead(None, "Cesar Augusto Perez Tafur", estado="en transito"),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico_tiktok == 5  # los 5 leads de César, sin excepción
    assert m.leads_organico == 0  # Suma 1 no se reparte a la tarjeta individual
    assert m.leads_tiktok == 0


def test_leads_organico_tiktok_generales_no_incluyen_a_cesar():
    """Leads de Orgánico/TikTok de OTROS asesores (no César) se cuentan normal
    vía Suma 2, sin verse afectados por la regla especial de César."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia"),
        _lead("Tiktok", "ana"),
        _lead("Clientify - Facebook", "Cesar Augusto Perez Tafur"),  # Suma 1, no Suma 2
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
# Regla: leads Orgánico/TikTok solo cuentan si "Motivo de no cierre" viene
# diligenciado (no aplica a Suma 1 / César, ni a leads_pauta, ni a
# asignados_organico/asignados_tiktok — ver has_motivo_diligenciado_mask)
# ---------------------------------------------------------------------------

def test_leads_organico_con_motivo_vacio_no_cuenta():
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo=None),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico == 0
    assert m.leads_organico_tiktok == 0


def test_leads_tiktok_con_motivo_vacio_no_cuenta():
    df = pd.DataFrame([
        _lead("Tiktok", "ana", motivo=None),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_tiktok == 0
    assert m.leads_organico_tiktok == 0


@pytest.mark.parametrize("motivo_vacio", ["", "nan", "none", "sin diligenciar", "NaN", "  "])
def test_leads_organico_variantes_de_motivo_vacio_no_cuentan(motivo_vacio):
    """Mismo set de valores 'vacíos' que usa is_qualified_mask (case/espacio
    insensible), para que el criterio de 'diligenciado' sea consistente."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo=motivo_vacio),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico == 0


def test_leads_organico_tiktok_motivo_mixto_solo_cuenta_los_diligenciados():
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo="cliente potencial"),   # cuenta
        _lead("Orgánico", "ana", motivo=None),                     # no cuenta
        _lead("Tiktok", "carlos", motivo="no se logró contactar"), # cuenta
        _lead("Tiktok", "juan", motivo=""),                        # no cuenta
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico == 1
    assert m.leads_tiktok == 1
    assert m.leads_organico_tiktok == 2


def test_leads_organico_tiktok_cesar_no_requiere_motivo_diligenciado():
    """Suma 1 (César) mantiene su regla 'sin importar canal ni estado' —
    el nuevo filtro de motivo diligenciado NO se le aplica, solo a la
    población general (Suma 2) de Orgánico/TikTok."""
    df = pd.DataFrame([
        _lead("Orgánico", "Cesar Augusto Perez Tafur", motivo=None),
        _lead("Tiktok", "Cesar Augusto Perez Tafur", motivo=""),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico_tiktok == 2
    assert m.leads_organico == 0
    assert m.leads_tiktok == 0


def test_asignados_organico_no_requiere_motivo_diligenciado():
    """El nuevo filtro solo restringe leads_organico/leads_tiktok (la
    tarjeta 'Leads Orgánicos y TikTok'), no asignados_organico/asignados_tiktok."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo=None),
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico == 0
    assert m.asignados_organico == 1


# ---------------------------------------------------------------------------
# Regla 2026-08-12c: "Calificados" es una regla ESTRICTA y SIN EXCEPCIONES —
# reemplaza toda la lógica de excepciones por canal/asesor de iteraciones
# anteriores (Orgánico/TikTok, redes sueltas, exención de César Augusto).
# Calificado ÚNICAMENTE si el motivo está en QUALIFIED_MOTIVES o hay un
# cierre real (Cantidad de cierres >= 1). Cualquier otro caso — motivo
# vacío/None/'sin diligenciar', o motivo en UNQUALIFIED_MOTIVES, sin cierre
# — es No calificado, sin importar canal ni asesor.
# ---------------------------------------------------------------------------

def test_calificados_motivo_vacio_no_cuenta_sin_importar_canal_ni_asesor():
    """Motivo vacío/None/'sin diligenciar' sin cierre real → SIEMPRE No
    calificado, para cualquier canal (Orgánico, TikTok, redes sueltas, Pauta
    paga oficial, Llamada, Formulario, Referido) y cualquier asesor."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo=None),
        _lead("Tiktok", "ana", motivo=""),
        _lead("Facebook", "carlos", motivo=None),            # canal social suelto
        _lead("Clientify - Facebook", "juan", motivo=None),  # pauta paga oficial
        _lead("Llamada Entrante", "maria", motivo=None),
        _lead("Formulario web", "pedro", motivo="sin diligenciar"),
        _lead("Referido externo", "laura", motivo=None),
    ])
    m = compute_all_metrics(df, df)
    assert m.calificados == 0
    assert m.no_calificados == 7


def test_calificados_motivo_qualified_diligenciado_si_cuenta():
    """Motivo en QUALIFIED_MOTIVES, diligenciado, sí califica — sin importar
    el canal."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo="cliente potencial"),
        _lead("Clientify - Facebook", "ana", motivo="cliente de seguimiento"),
    ])
    m = compute_all_metrics(df, df)
    assert m.calificados == 2
    assert m.no_calificados == 0


def test_calificados_motivo_unqualified_no_cuenta_sin_importar_canal():
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo="no se logró contactar"),
        _lead("Clientify - Facebook", "ana", motivo="su caso no aplicaba"),
    ])
    m = compute_all_metrics(df, df)
    assert m.calificados == 0
    assert m.no_calificados == 2


def test_calificados_cierre_real_cuenta_sin_importar_motivo_ni_canal():
    """Un cierre real siempre califica, incluso con motivo vacío."""
    lead = _lead("Orgánico", "sofia", motivo=None)
    lead["Cantidad de cierres"] = 1.0
    df = pd.DataFrame([lead])
    m = compute_all_metrics(df, df)
    assert m.calificados == 1
    assert m.no_calificados == 0


def test_calificados_cesar_excluido_por_completo_de_asignados():
    """SUPERSEDE la regla 2026-08-12c (abajo el historial): esa iteración
    solo quitó la excepción de César DENTRO de `is_qualified_mask` (motivo
    vacío sin cierre → no_calificados=1, igual que cualquier asesor). La
    regla 2026-09-03 va más allá: César se excluye COMPLETO del universo de
    Asignados (`asignado_mask` en `compute_all_metrics`, exclusión LOCAL —
    `is_qualified_mask`/`is_asesor_comercial` no se tocaron), así que ahora
    no aporta NI a calificados NI a no_calificados — sigue completo en la
    bolsa 'Leads Orgánicos y TikTok' (Suma 1), que no se tocó en este cambio."""
    df = pd.DataFrame([
        _lead("Orgánico", "Cesar Augusto Perez Tafur", motivo=None),
    ])
    m = compute_all_metrics(df, df)
    assert m.asignados == 0
    assert m.calificados == 0
    assert m.no_calificados == 0
    assert m.leads_organico_tiktok == 1


def test_asignados_calificados_no_calificados_excluyen_a_cesar_augusto_salvo_cierre_real():
    """Regla 2026-09-03b: César se excluye de Asignados/Calificados/No
    calificados SALVO que haya tenido un cierre real ('Cantidad de cierres'
    >= 1) — en ese caso SÍ cuenta en Asignados, y automáticamente en
    Calificados (la misma señal de cierre real que lo mete a Asignados es
    la que usa `is_qualified_mask` para calificarlo). Un asesor comercial
    normal, para contraste, sigue entrando sin cambios."""
    _base = {
        "canal online": None, "Canal offline": "Orgánico", "Origen de la pauta": None,
        "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        "estado": "en transito",
    }
    df = pd.DataFrame([
        # César sin motivo diligenciado ni cierre real → excluido de Asignados.
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "Cesar Augusto Perez Tafur",
         "Motivo de no cierre": None, "Cantidad de cierres": None, "Fecha de cierre": pd.NaT},
        # César CON cierre real → SÍ entra a Asignados, y a Calificados.
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "Cesar Augusto Perez Tafur",
         "Motivo de no cierre": None, "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5)},
        # Asesor comercial normal, calificado — para contraste, sin cambios.
        {**_base, "creado": datetime(2026, 4, 3), "propietario": "Sofia de la Hoz",
         "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": None, "Fecha de cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    # Asignados = César-con-cierre + Sofía (César-sin-cierre queda afuera).
    assert m.asignados == 2
    # Calificados = ambos: César por cierre real, Sofía por motivo QUALIFIED.
    assert m.calificados == 2
    assert m.no_calificados == 0


def test_leads_organico_tiktok_sigue_exigiendo_organico_estricto_y_motivo():
    """Rule 1 (sin cambios en esta iteración): la bolsa 'Leads Orgánicos y
    TikTok' exige ser ESTRICTAMENTE Orgánico/TikTok Y tener el motivo
    diligenciado. Un canal social suelto (Facebook/Instagram) no cuenta ahí
    aunque venga diligenciado — solo Orgánico/TikTok literal."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", motivo="cliente potencial"),   # sí cuenta
        _lead("Orgánico", "ana", motivo=None),                     # no cuenta: sin motivo
        _lead("Facebook", "carlos", motivo="cliente potencial"),   # no cuenta: no es Orgánico/TikTok
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico == 1
    assert m.leads_organico_tiktok == 1
    assert m.leads_pauta == 3  # los 3 (Facebook y ambos Orgánico) siguen siendo Pauta


# ---------------------------------------------------------------------------
# Regla 2026-08-12d: la regla de Calificados/Leads Orgánicos y TikTok NO
# depende del mes — ni `is_qualified_mask` ni `has_motivo_diligenciado_mask`
# reciben año/mes como parámetro, así que no existe (ni puede existir) un
# filtro condicional tipo "solo aplica a agosto". Se verifica explícitamente
# aquí porque el usuario reportó que el acumulado general parecía seguir
# usando la regla vieja para meses distintos de agosto.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mes", [
    datetime(2024, 5, 1),   # FOUNDING_DATE
    datetime(2025, 1, 1),
    datetime(2026, 3, 1),
    datetime(2026, 7, 1),
    datetime(2026, 8, 1),   # mes en curso (hoy 2026-08-12)
    datetime(2026, 12, 1),
])
def test_calificados_regla_estricta_es_igual_en_cualquier_mes(mes):
    """Mismo patrón de leads (2 sin motivo/sin cierre → No calificado, 1 con
    motivo QUALIFIED → Calificado) debe dar el MISMO resultado sin importar
    el mes de 'creado' — no hay ninguna condición temporal en la regla."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", creado=mes, motivo=None),
        _lead("Clientify - Facebook", "ana", creado=mes, motivo=None),
        _lead("Orgánico", "carlos", creado=mes, motivo="cliente potencial"),
    ])
    m = compute_all_metrics(df, df)
    assert m.calificados == 1, f"Falló para mes={mes}"
    assert m.no_calificados == 2, f"Falló para mes={mes}"


@pytest.mark.parametrize("mes", [
    datetime(2024, 5, 1), datetime(2026, 1, 1), datetime(2026, 8, 1),
])
def test_leads_organico_tiktok_motivo_diligenciado_es_igual_en_cualquier_mes(mes):
    """La bolsa 'Leads Orgánicos y TikTok' exige motivo diligenciado igual en
    cualquier mes — no depende de la fecha de 'creado'."""
    df = pd.DataFrame([
        _lead("Orgánico", "sofia", creado=mes, motivo=None),           # no cuenta
        _lead("Tiktok", "ana", creado=mes, motivo="cliente potencial"),  # cuenta
    ])
    m = compute_all_metrics(df, df)
    assert m.leads_organico == 0, f"Falló para mes={mes}"
    assert m.leads_tiktok == 1, f"Falló para mes={mes}"
    assert m.leads_organico_tiktok == 1, f"Falló para mes={mes}"


def test_is_qualified_mask_no_depende_de_fecha_ni_mes():
    """Verificación estructural: `is_qualified_mask` solo recibe `df` (ni
    año ni mes) y su código fuente no contiene ninguna referencia a fechas,
    'creado', ni nombres de mes — no puede existir un filtro condicional
    tipo 'if mes == agosto' porque la función no tiene forma de saber en
    qué mes está evaluando."""
    import inspect
    from src.analytics import metrics as metrics_module

    sig = inspect.signature(metrics_module.is_qualified_mask)
    assert list(sig.parameters) == ["df"], (
        "is_qualified_mask no debe recibir año/mes como parámetro"
    )
    source = inspect.getsource(metrics_module.is_qualified_mask)
    prohibidos = ["year", "month", "creado", "agosto", "date(", "Timestamp("]
    encontrados = [p for p in prohibidos if p in source]
    assert not encontrados, (
        f"is_qualified_mask no debe depender de fechas/meses, se encontró: {encontrados}"
    )


# ---------------------------------------------------------------------------
# Eficiencias
# ---------------------------------------------------------------------------

def test_eficiencia_real_calculo_correcto():
    """100 leads pauta asignados a Asesor Comercial, 5 con cierre válido en el mes.
    Todos calificados (motivo QUALIFIED diligenciado) → eficiencia_real = 5*100/100 = 5.0%."""
    leads = []
    for i in range(95):
        leads.append({
            "creado": datetime(2026, 4, 1), "propietario": "asesor", "estado": "en transito",
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook", "Motivo de no cierre": "cliente potencial",
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
    assert m.calificados == 100
    assert m.eficiencia_real == pytest.approx(5.0)  # (5*100)/100


def test_eficiencia_bruta_formula():
    """Eficiencia Bruta = Cierres(Pauta+Organico)*100 / (AsignadosPauta+Organico+TikTok+Calificados+NoCalificados)."""
    df = pd.DataFrame([
        # Pauta, asignado, calificado, con cierre válido
        {"creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": _ACTIVO,
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Orgánico — motivo diligenciado para que cuente en leads_organico
        # (ver has_motivo_diligenciado_mask); no es el foco de este test.
        {"creado": datetime(2026, 4, 2), "propietario": "ana", "estado": "en transito",
         "canal online": None, "Canal offline": "orgánico",
         "Origen de la pauta": None, "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    # 2026-07-03e: asignados_pauta ahora es 2 (facebook + orgánico, ambos
    # Pauta), leads_organico=1, leads_tiktok=0, calificados=2, no_calificados=0
    # denom = 2+1+0+2+0 = 5; numerador = total_cierres = 1 (solo sofia cerró)
    assert m.eficiencia_bruta == pytest.approx(1 * 100 / 5)


# ---------------------------------------------------------------------------
# Tarjetas KPI
# ---------------------------------------------------------------------------

def test_get_kpi_definitions_todos_devuelve_11_tarjetas():
    """Layout de 11 tarjetas (2026-09-03c): las 3 tarjetas de cierres por
    orden de cierre (Pauta(M)/Referidos(R)/Adicionales) fueron reemplazadas
    por 4 tarjetas desglosadas por canal Y por primer-cierre-vs-re-cierre."""
    from src.analytics.kpis import get_kpi_definitions
    assert len(get_kpi_definitions("Todos")) == 13


def test_kpi_todos_incluye_tarjetas_en_orden_2026_09_03c():
    """Orden (2026-09-03c, eficiencias renombradas 2026-07-03i; 2 tarjetas de
    Canal offline agregadas 2026-09-04): Creados, Leads Organico+TikTok
    (unificado), Calificados, No calificados, Cierres de Pauta (Total),
    Cierres de Referidos (Total), Re-cierres de Pauta, Re-cierres de
    Referidos, Total Cierres, % Eficiencia Real, % Eficiencia Bruta, Leads
    Clientify WhatsApp, Leads Formulario Facebook-CP.

    Las 3 tarjetas de cierres por orden de cierre (2026-07-03c) fueron
    reemplazadas por 4 tarjetas por canal — "Cierres de Pauta (Total)"
    (cierres_marketing) y "Cierres de Referidos (Total)" (cierres_referidos)
    ya suman las 4 columnas de fecha de cierre, no solo la 1ra; "Re-cierres
    de Pauta"/"Re-cierres de Referidos" son cierres_adicionales_pauta/
    cierres_adicionales_referido (solo 2da/3ra/4ta columna). "Total Cierres"
    sigue usando total_cierres_estricto, sin cambios. "% Eficiencia Pauta"
    se renombró a "% Eficiencia Real" (campo eficiencia_real) en 2026-07-03i.
    El label de eficiencia_global pasó de "% Eficiencia Global" a
    "% Eficiencia Bruta" en 2026-09-04 (el campo interno NO se renombró)."""
    from src.analytics.kpis import KPI_DEFINITIONS_TODOS
    keys = [k.key for k in KPI_DEFINITIONS_TODOS]
    assert keys == [
        "creados", "leads_organico_tiktok",
        "calificados", "no_calificados",
        "cierres_marketing", "cierres_referidos",
        "cierres_adicionales_pauta", "cierres_adicionales_referido",
        "total_cierres_estricto",
        "eficiencia_real", "eficiencia_global",
        "leads_clientify_whatsapp", "leads_formulario_facebook_cp",
    ]


def test_kpi_todos_no_incluye_lideres_pauta_ni_leads_pauta():
    """Ni 'Líderes Pauta' (nunca existió) ni 'Leads Pauta' (reemplazada) deben
    aparecer en el layout de 13 tarjetas."""
    from src.analytics.kpis import KPI_DEFINITIONS_TODOS
    labels = [k.label for k in KPI_DEFINITIONS_TODOS]
    assert "Líderes Pauta" not in labels
    assert "Leads Pauta" not in labels
    assert len(KPI_DEFINITIONS_TODOS) == 13


def test_kpi_todos_tarjetas_de_cierre_van_consecutivas_antes_del_total():
    """Pauta(Total) -> Referidos(Total) -> Re-cierres Pauta -> Re-cierres
    Referidos -> Total Cierres, en ese orden y consecutivas."""
    from src.analytics.kpis import KPI_DEFINITIONS_TODOS
    keys = [k.key for k in KPI_DEFINITIONS_TODOS]
    i = keys.index("cierres_marketing")
    assert keys[i:i + 5] == [
        "cierres_marketing", "cierres_referidos",
        "cierres_adicionales_pauta", "cierres_adicionales_referido",
        "total_cierres_estricto",
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


def test_cierres_no_pauta_es_solo_referido_puro_sin_fuga():
    """2026-07-03e: cierres_no_pauta = cierres_referidos (Orgánico/TikTok ya
    son Pauta, no 'no pauta'). La identidad Cierres Pauta(M) + Cierres
    Referidos(R) == total_cierres_general debe seguir cumpliéndose siempre
    (partición binaria completa, sin fuga ni doble conteo)."""
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
    assert m.cierres_marketing == 3  # facebook + orgánico + tiktok (los 3 son Pauta)
    assert m.cierres_no_pauta == 1   # solo el referido puro
    assert m.cierres_marketing + m.cierres_no_pauta == m.total_cierres_general == 4


def test_eficiencia_real_usa_calificados_del_mes_no_calificados_pauta():
    """2026-07-03i: % Eficiencia Real (antes '% Eficiencia Pauta') =
    (Cierres de Pauta * 100) / Calificados del MES TOTAL — ya no
    calificados_pauta ni asignados."""
    df = pd.DataFrame([
        # Pauta, calificada (motivo vacío), con cierre válido
        {"creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": _ACTIVO,
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Pauta, NO calificada (motivo explícito UNQUALIFIED), sin cierre
        {"creado": datetime(2026, 4, 2), "propietario": "ana", "estado": "en transito",
         "canal online": "paid social", "Canal offline": "clientify - instagram",
         "Origen de la pauta": "instagram", "Motivo de no cierre": "no se logró contactar",
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido, calificada (motivo QUALIFIED diligenciado) — infla calificados TOTAL sin ser Pauta
        {"creado": datetime(2026, 4, 3), "propietario": "carlos", "estado": "en transito",
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    assert m.calificados_pauta == 1
    assert m.calificados == 2  # sofia + carlos (ana no calificó)
    assert m.cierres_marketing == 1
    # Con calificados_pauta (fórmula vieja) daría 100%; con calificados TOTAL (nueva) da 50%.
    assert m.eficiencia_real == pytest.approx(1 * 100 / 2)


def test_eficiencia_global_usa_creados_no_calificados():
    """2026-07-03i: % Eficiencia Global = (Cierres de Pauta * 100) / Leads
    CREADOS del mes — ya no total de cierres/calificados.

    2026-09-08: 'creados' ahora excluye Referido puro (ver test_creados),
    así que se agrega una 4ta fila Pauta sin calificar para que 'creados'
    siga siendo distinto de 'calificados' en este fixture (si no, ambos
    quedarían en 2 por coincidencia y el test dejaría de probar la
    distinción creados-vs-calificados que es su propósito original)."""
    df = pd.DataFrame([
        # Pauta, calificada, con cierre válido
        {"creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": _ACTIVO,
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook", "Motivo de no cierre": None,
         "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 4, 5),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Pauta, NO calificada, sin cierre — infla creados sin ser calificado
        {"creado": datetime(2026, 4, 2), "propietario": "ana", "estado": "en transito",
         "canal online": "paid social", "Canal offline": "clientify - instagram",
         "Origen de la pauta": "instagram", "Motivo de no cierre": "no se logró contactar",
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido, calificada (motivo QUALIFIED diligenciado), sin cierre —
        # ya NO cuenta para 'creados' (Referido puro), sí para 'calificados'.
        {"creado": datetime(2026, 4, 3), "propietario": "carlos", "estado": "en transito",
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Motivo de no cierre": "cliente potencial",
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Pauta, NO calificada, sin cierre — 2do lead Pauta sin calificar,
        # para que creados (3) siga siendo distinto de calificados (2).
        {"creado": datetime(2026, 4, 4), "propietario": "diego", "estado": "en transito",
         "canal online": "paid social", "Canal offline": "clientify - whatsapp",
         "Origen de la pauta": None, "Motivo de no cierre": "no se logró contactar",
         "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    assert m.creados == 3
    assert m.calificados == 2
    assert m.cierres_marketing == 1
    # Con calificados (fórmula anterior) daría 50%; con creados (nueva) da 33.3%.
    assert m.eficiencia_global == pytest.approx(1 * 100 / 3)


def test_eficiencia_real_y_global_ya_vienen_en_puntos_porcentuales():
    """eficiencia_real/eficiencia_global se muestran con format_percent_raw (sin
    re-multiplicar por 100) porque la fórmula del negocio ya incluye el *100."""
    from src.utils.formatters import format_percent_raw
    assert format_percent_raw(5.0) == "5.0%"


# ---------------------------------------------------------------------------
# Bolsa "Leads Orgánicos y TikTok" — regla César corregida (2026-07-03)
# ---------------------------------------------------------------------------

def test_is_cesar_augusto_es_insensible_a_tildes():
    """'César' (con tilde) y 'Cesar' (sin tilde) deben matchear igual: el
    Excel puede traer cualquiera de las dos formas según quién lo tipeó."""
    assert is_cesar_augusto({"propietario": "César Augusto Pérez Tafur"}) is True
    assert is_cesar_augusto({"propietario": "Cesar Augusto Perez Tafur"}) is True


# ---------------------------------------------------------------------------
# Tarjetas de cierre desglosadas (2026-07-03c): Pauta(M) / Referidos(R) /
# Adicionales / Total Cierres estricto
# ---------------------------------------------------------------------------

def test_total_cierres_estricto_es_la_suma_de_las_3_tarjetas_de_cierre():
    """Por construcción: Total Cierres = Cierres Pauta(M) + Cierres Referidos(R)
    + Cierres Adicionales. Nunca debe calcularse por un camino separado."""
    _base = {
        "Motivo de no cierre": None, "Cantidad de cierres": 2.0, "estado": _ACTIVO,
    }
    df = pd.DataFrame([
        # Pauta: 1er cierre en abril + 2do cierre (re-cierre) también en abril
        {**_base, "creado": datetime(2026, 4, 1), "propietario": "sofia",
         "canal online": "paid social", "Canal offline": "clientify - facebook",
         "Origen de la pauta": "facebook",
         "Fecha de cierre": datetime(2026, 4, 5),
         "Fecha de segundo cierre": datetime(2026, 4, 20),
         "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Referido: 1er cierre en abril
        {**_base, "creado": datetime(2026, 4, 2), "propietario": "ana",
         "canal online": "inbox-referral", "Canal offline": "referido - amigo",
         "Origen de la pauta": None, "Cantidad de cierres": 1.0,
         "Fecha de cierre": datetime(2026, 4, 10), "Fecha de segundo cierre": pd.NaT,
         "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        # Orgánico: 1er cierre en abril (cae en el bucket "Pauta (M)" porque
        # Orgánico ahora es Pauta — regla 2026-07-03e).
        {**_base, "creado": datetime(2026, 4, 3), "propietario": "carlos",
         "canal online": "inbox", "Canal offline": "orgánico",
         "Origen de la pauta": None, "Cantidad de cierres": 1.0,
         "Fecha de cierre": datetime(2026, 4, 12), "Fecha de segundo cierre": pd.NaT,
         "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    m = compute_all_metrics(df, df)
    assert m.cierres_pauta_primer == 2     # sofia (facebook) + carlos (orgánico)
    assert m.cierres_referido_primer == 1  # ana (referido puro)
    assert m.cierres_adicionales == 1      # 2do cierre de sofia en abril
    assert m.total_cierres_estricto == 4
    assert m.total_cierres_estricto == (
        m.cierres_pauta_primer + m.cierres_referido_primer + m.cierres_adicionales
    )
    # Debe coincidir con total_cierres_general (mismo universo de cierres
    # válidos, solo particionado distinto: por canal vs. por orden de cierre).
    assert m.total_cierres_estricto == m.total_cierres_general


def test_total_cierres_estricto_excluye_estado_inactivo():
    """La Regla de Cierre Válido (estado != 'inactivo') también aplica a la
    tarjeta 'Total Cierres' estricta, vía cierres_pauta_primer/referido_primer/adicionales."""
    _base = {
        "propietario": "sofia", "Motivo de no cierre": None, "Cantidad de cierres": 1.0,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook",
        "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT,
        "Fecha de 4to cierre": pd.NaT,
    }
    df = pd.DataFrame([
        {**_base, "creado": datetime(2026, 4, 1), "estado": "inactivo",
         "Fecha de cierre": datetime(2026, 4, 5)},
    ])
    m = compute_all_metrics(df, df)
    assert m.cierres_pauta_primer == 0
    assert m.total_cierres_estricto == 0


def test_desglose_cierres_por_etapa_respeta_regla_estado_inactivo():
    """Los 4 números del expander 'Desglose de cierres por etapa'
    (cierres_1..cierres_4) deben excluir solo estado == 'inactivo', igual
    que el resto de cierres — no una regla de validez distinta."""
    _base = {
        "propietario": "sofia", "Motivo de no cierre": None, "Cantidad de cierres": 4.0,
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook",
    }
    df = pd.DataFrame([
        # Estado intermedio (ni activo ni inactivo): las 4 columnas deben contar.
        {**_base, "creado": datetime(2026, 4, 1), "estado": "en proceso de firma",
         "Fecha de cierre": datetime(2026, 4, 1),
         "Fecha de segundo cierre": datetime(2026, 4, 2),
         "Fecha de tercer cierre": datetime(2026, 4, 3),
         "Fecha de 4to cierre": datetime(2026, 4, 4)},
    ])
    m = compute_all_metrics(df, df)
    assert (m.cierres_1, m.cierres_2, m.cierres_3, m.cierres_4) == (1, 1, 1, 1)

    df_inactivo = df.copy()
    df_inactivo.loc[0, "estado"] = "inactivo"
    m_inactivo = compute_all_metrics(df_inactivo, df_inactivo)
    assert (m_inactivo.cierres_1, m_inactivo.cierres_2, m_inactivo.cierres_3, m_inactivo.cierres_4) == (0, 0, 0, 0)
