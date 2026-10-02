import pandas as pd

from src.data_sources.base import normalize_contacts_df
from src.data_sources.clientify_api import CUSTOM_FIELD_NAMES, _build_dataframe

# Fixture de 2 contactos con la MISMA forma que la API real devolvió en el
# diagnóstico (scripts/diagnostic_api_schema.py) — custom_fields inline,
# contact_source anidado, tags como lista, medium="social-paid".
API_CONTACTS_FIXTURE = [
    {
        "id": 1,
        "owner": "ana.perdomo@solucionesmigratoriassm.com",
        "owner_name": "Ana Perdomo",
        "status": "client",
        "medium": "social-paid",
        "channel": "inbox_whatsapp",
        "contact_source": {"name": "Clientify - Whatsapp"},
        "tags": ["facebook-ads-lead", "whatsapp 305-508-5147"],
        "first_name": "Maria",
        "last_name": "Gomez",
        "birthday": "1985-02-13",
        "addresses": [{"city": "Miami", "state": "Florida", "country": "Estados Unidos", "postal_code": "33101"}],
        "contact_sector": "Construcción - Incluye obreros, carpinteros, plomeros y electricistas.",
        "custom_fields": [
            {"field": "Origen de la pauta", "value": "Facebook"},
            {"field": "Motivo de no cierre", "value": "Cliente potencial"},
            {"field": "Cantidad de cierres", "value": "1"},
            {"field": "Fecha de cierre", "value": "02/06/2026"},
            {"field": "Valor total del proceso", "value": "6000"},
            {"field": "Cuota inicial pactada", "value": "1000"},
            {"field": "Tipo de proceso", "value": "Permiso de Trabajo"},
            {"field": "Campaña - pauta", "value": "Campaña Julio"},
            {"field": "Publicacion por la que se contacto el cliente", "value": "No aplica/Fue referido"},
        ],
        "created": "2026-06-03T00:20:51.072939+02:00",
    },
    {
        "id": 2,
        "owner": "uriel.ortega@solucionesmigratoriassm.com",
        "owner_name": None,  # contacto sin asesor asignado
        "status": "cold-lead",
        "medium": "",
        "channel": "manual",
        "contact_source": {},  # sin Canal offline
        "tags": [],
        "first_name": None,
        "last_name": None,
        "birthday": None,
        "addresses": [],  # sin direcciones cargadas
        "contact_sector": None,
        "custom_fields": [],  # sin ningun custom field cargado
        "created": "2026-09-19T17:36:59.887305+02:00",
    },
]


def _excel_fixture() -> pd.DataFrame:
    """DataFrame crudo (pre-normalización) con la misma forma que produce
    `pd.read_excel` sobre un export real, para comparar esquema contra la API.
    """
    return pd.DataFrame({
        "creado": [pd.Timestamp("2026-06-03 00:20:51"), pd.Timestamp("2026-09-19 17:36:59")],
        "propietario": ["Ana Perdomo", float("nan")],
        "canal online": ["paid social", ""],
        "Canal offline": ["Clientify - Whatsapp", float("nan")],
        "estado": ["activo", "activo"],
        "Etiquetas": ["facebook-ads-lead, whatsapp 305-508-5147", ""],
        "Origen de la pauta": ["Facebook", float("nan")],
        "Motivo de no cierre": ["Cliente potencial", float("nan")],
        "Cantidad de cierres": [1.0, float("nan")],
        "Fecha de cierre": [pd.Timestamp("2026-06-02"), pd.NaT],
        "Fecha de segundo cierre": [pd.NaT, pd.NaT],
        "Fecha de tercer cierre": [pd.NaT, pd.NaT],
        "Fecha de 4to cierre": [pd.NaT, pd.NaT],
        "Valor total del proceso": [6000.0, float("nan")],
        "Valor total segundo cierre": [float("nan"), float("nan")],
        "Valor total tercer cierre": [float("nan"), float("nan")],
        "Valor total 4to cierre": [float("nan"), float("nan")],
        "Cuota inicial pactada": [1000.0, float("nan")],
        "Cuota inicial segundo cierre": [float("nan"), float("nan")],
        "Cuota inicial tercer cierre": [float("nan"), float("nan")],
        "Cuota inicial 4to cierre": [float("nan"), float("nan")],
        # Demografía/ubicación/atribución — ninguna de estas 6 está en
        # `base.DATE_COLS`/`TEXT_COLS`, así que en un export real de Clientify
        # llegan tal cual como texto (igual que las 4 "Fecha de..." de arriba
        # ANTES de que `normalize_contacts_df` las parsee — de ahí que esas sí
        # necesiten `dayfirst=True` en vez de venir ya como Timestamp nativo).
        "cumpleaños": ["13/02/1985", float("nan")],
        "nombre": ["Maria Gomez", float("nan")],
        "ciudad 1": ["Miami", float("nan")],
        "provincia/estado 1": ["Florida", float("nan")],
        "país": ["Estados Unidos", float("nan")],
        "sector": ["Construcción - Incluye obreros, carpinteros, plomeros y electricistas.", float("nan")],
        "Tipo de proceso": ["Permiso de Trabajo", float("nan")],
        "Campaña - pauta": ["Campaña Julio", float("nan")],
        "Publicacion por la que se contacto el cliente": ["No aplica/Fue referido", float("nan")],
    })


def test_columnas_coinciden_exactamente_entre_api_y_excel():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    excel_df = normalize_contacts_df(_excel_fixture())

    assert set(api_df.columns) == set(excel_df.columns)


def test_dtypes_coinciden_exactamente_entre_api_y_excel():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    excel_df = normalize_contacts_df(_excel_fixture())

    for col in excel_df.columns:
        assert api_df[col].dtype == excel_df[col].dtype, (
            f"dtype de '{col}' difiere: API={api_df[col].dtype} vs Excel={excel_df[col].dtype}"
        )


def test_medium_social_paid_se_remapea_a_paid_social():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "canal online"] == "paid social"


def test_custom_fields_numericos_quedan_castados_y_nan_si_faltan():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "Cantidad de cierres"] == 1.0
    assert pd.isna(api_df.loc[1, "Cantidad de cierres"])  # contacto 2 no tiene custom_fields


def test_fecha_de_cierre_queda_parseada_como_datetime_dayfirst():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "Fecha de cierre"] == pd.Timestamp("2026-06-02")


def test_etiquetas_lista_se_une_en_string_para_str_contains():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert "305-508-5147" in api_df.loc[0, "Etiquetas"]


def test_propietario_ausente_queda_como_nan_no_como_string_none():
    """Regresión: funnel.py hace df["propietario"].isna() (vectorizado, no vía
    _safe_str) para armar la fila 'Sin asesor' — un owner_name=None sin
    normalizar quedaría como el string literal "none" y rompería ese filtro.
    """
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df["propietario"].isna().iloc[1]


def test_canal_offline_ausente_queda_como_nan():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df["Canal offline"].isna().iloc[1]


def test_estado_placeholder_nunca_es_inactivo():
    from src.config.settings import CIERRE_INVALID_ESTADOS

    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert not api_df["estado"].isin(CIERRE_INVALID_ESTADOS).any()


def test_build_dataframe_con_lista_vacia_no_rompe():
    df = _build_dataframe([])
    assert df.empty
    assert set(CUSTOM_FIELD_NAMES).issubset(set(df.columns))
    assert {"cumpleaños", "nombre", "ciudad 1", "provincia/estado 1", "país", "sector"}.issubset(set(df.columns))


# --- Las 9 columnas de demografía/ubicación/atribución agregadas en esta
# ronda de mapeo (auditoría de columnas + verificación empírica contra la API
# real, ver scratch/api_sample_contactos.json / api_custom_fields_catalog.json
# / api_sector_crosscheck_contacts.json) ---

def test_cumpleanos_toma_birthday_nativo():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "cumpleaños"] == "1985-02-13"
    assert pd.isna(api_df.loc[1, "cumpleaños"])  # contacto 2: birthday=None


def test_nombre_concatena_first_name_y_last_name():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "nombre"] == "Maria Gomez"


def test_nombre_ausente_queda_como_nan_no_como_string_con_espacio_colgante():
    """Regresión: si first_name/last_name faltan, `f"{first} {last}".strip()`
    con strings vacíos daría "" — debe quedar NaN, no un string vacío que
    rompería `.isna()` aguas abajo (mismo patrón que `_to_nan_if_blank`)."""
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df["nombre"].isna().iloc[1]


def test_sector_toma_contact_sector_nativo_sin_transformacion():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "sector"] == "Construcción - Incluye obreros, carpinteros, plomeros y electricistas."
    assert pd.isna(api_df.loc[1, "sector"])  # contacto 2: contact_sector=None


def test_ciudad_provincia_pais_toman_addresses_0():
    """`ciudad 1`/`provincia/estado 1`/`país` NO están en `base.TEXT_COLS`,
    así que `normalize_contacts_df` no las toca (igual que en el Excel) —
    quedan con el valor tal cual vino de `addresses[0]`, sin lower/strip."""
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "ciudad 1"] == "Miami"
    assert api_df.loc[0, "provincia/estado 1"] == "Florida"
    assert api_df.loc[0, "país"] == "Estados Unidos"


def test_tipo_de_proceso_campana_pauta_y_publicacion_via_custom_fields():
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df.loc[0, "Tipo de proceso"] == "Permiso de Trabajo"
    assert api_df.loc[0, "Campaña - pauta"] == "Campaña Julio"
    assert api_df.loc[0, "Publicacion por la que se contacto el cliente"] == "No aplica/Fue referido"
    # Contacto 2 no tiene ninguno de estos 3 custom fields cargados -> NaN.
    assert pd.isna(api_df.loc[1, "Tipo de proceso"])
    assert pd.isna(api_df.loc[1, "Campaña - pauta"])
    assert pd.isna(api_df.loc[1, "Publicacion por la que se contacto el cliente"])


def test_direccion_con_addresses_vacio_queda_nan_no_string_vacio():
    """addresses=[] (lista vacía, contacto 2 del fixture) -> NaN, no ''."""
    api_df = normalize_contacts_df(_build_dataframe(API_CONTACTS_FIXTURE))
    assert api_df["ciudad 1"].isna().iloc[1]
    assert api_df["provincia/estado 1"].isna().iloc[1]
    assert api_df["país"].isna().iloc[1]


def test_direccion_con_addresses_ausente_no_rompe():
    """addresses ni siquiera está como clave en el contacto (distinto del
    caso `addresses=[]` de arriba) -> debe seguir devolviendo NaN, no lanzar
    KeyError/AttributeError."""
    contact = {
        "id": 99,
        "owner_name": None,
        "medium": "",
        "contact_source": {},
        "tags": [],
        "custom_fields": [],
        "created": "2026-09-19T17:36:59.887305+02:00",
        # sin clave "addresses" en absoluto
    }
    df = _build_dataframe([contact])
    assert pd.isna(df.loc[0, "ciudad 1"])
    assert pd.isna(df.loc[0, "provincia/estado 1"])
    assert pd.isna(df.loc[0, "país"])


def test_direccion_con_campo_puntual_en_blanco_queda_nan():
    """`addresses` trae 1 elemento, pero city/state/country vienen vacíos
    dentro de ese elemento (patrón real confirmado: 8/15 de los contactos
    con addresses no vacío en la muestra real tenían city="" pese a tener
    street poblado) -> NaN, no string vacío."""
    contact = {
        "id": 100,
        "owner_name": None,
        "medium": "",
        "contact_source": {},
        "tags": [],
        "custom_fields": [],
        "created": "2026-09-19T17:36:59.887305+02:00",
        "addresses": [{"street": "123 Main St", "city": "", "state": "", "country": ""}],
    }
    df = _build_dataframe([contact])
    assert pd.isna(df.loc[0, "ciudad 1"])
    assert pd.isna(df.loc[0, "provincia/estado 1"])
    assert pd.isna(df.loc[0, "país"])


# La paginación de `_fetch_all_contacts` (ahora paralelizada con
# ThreadPoolExecutor) tiene sus propios tests dedicados en
# tests/test_clientify_api_pagination.py — no se duplican acá.
