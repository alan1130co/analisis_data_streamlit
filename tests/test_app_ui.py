"""Tests UI de extremo a extremo para `app.py`.

Usa `streamlit.testing.v1.AppTest` (mismo harness que
`tests/test_funnel_ui.py`/`tests/test_data_source_selector_ui.py`).

Cubre 2 regresiones reales encontradas en la integración con la API de
Clientify:

1. "Segmentación Clave" (TAB 2) fallaba con "La columna 'X' no existe en los
   datos cargados" para varias secciones (Tipo de proceso, país, provincia/
   estado, ciudad, sector, cumpleaños) cuando la fuente era la API, porque el
   mapeo de `ClientifyAPIClient` no cubría esas 9 columnas todavía — ver
   `src/data_sources/clientify_api.py` y la memoria del proyecto
   (`clientify_business_rules.md`, entrada 2026-09-30c).
2. La pestaña "Marketing e Inversión" (TAB 1) quedaba bloqueada detrás del
   spinner de sync de contactos, incluso para la gráfica de gasto en pauta
   que NO depende de ningún contacto de Clientify — `app.py` llamaba a
   `render_data_source_selector()` (potencialmente bloqueante, sync
   completo de la API) ANTES de renderizar esa gráfica.
"""
import pandas as pd
from streamlit.testing.v1 import AppTest


def _full_schema_fake_api_df() -> pd.DataFrame:
    """DataFrame con las 30 columnas que hoy mapea `ClientifyAPIClient`
    (núcleo de embudo/cierres + las 9 de demografía/ubicación/atribución
    agregadas en 2026-09-30c) — para ejercitar TODAS las secciones de
    "Segmentación Clave" sin depender del archivo real (gitignored) en
    `scratch/`."""
    return pd.DataFrame({
        "creado": [pd.Timestamp("2026-06-03")],
        "propietario": ["ana perdomo"],
        "canal online": ["paid social"],
        "Canal offline": ["clientify - whatsapp"],
        "estado": ["sin definir (api)"],
        "Etiquetas": [""],
        "Origen de la pauta": ["facebook"],
        "Motivo de no cierre": ["cliente potencial"],
        "Cantidad de cierres": [1.0],
        "Fecha de cierre": [pd.Timestamp("2026-06-02")],
        "Fecha de segundo cierre": [pd.NaT],
        "Fecha de tercer cierre": [pd.NaT],
        "Fecha de 4to cierre": [pd.NaT],
        "Valor total del proceso": [6000.0],
        "Valor total segundo cierre": [float("nan")],
        "Valor total tercer cierre": [float("nan")],
        "Valor total 4to cierre": [float("nan")],
        "Cuota inicial pactada": [1000.0],
        "Cuota inicial segundo cierre": [float("nan")],
        "Cuota inicial tercer cierre": [float("nan")],
        "Cuota inicial 4to cierre": [float("nan")],
        "cumpleaños": ["13/02/1985"],
        "nombre": ["Maria Gomez"],
        "ciudad 1": ["Miami"],
        "provincia/estado 1": ["Florida"],
        "país": ["Estados Unidos"],
        "sector": ["Construcción - Incluye obreros, carpinteros, plomeros y electricistas."],
        "Tipo de proceso": ["Permiso de Trabajo"],
        "Campaña - pauta": ["Campaña Julio"],
        "Publicacion por la que se contacto el cliente": ["No aplica/Fue referido"],
    })


def _build_app_with_fake_api_client():
    def app():
        import pandas as pd
        from tests.test_app_ui import _full_schema_fake_api_df
        from src.ui import api_source, data_source_selector, meta_ads_source
        from src.ui.data_source_selector import API_OPTION

        class _FakeClient:
            def __init__(self, token=None, base_url=None):
                pass

            def load(self):
                return _full_schema_fake_api_df()

        api_source.ClientifyAPIClient = _FakeClient
        api_source.CLIENTIFY_API_TOKEN = "fake-token-para-test-app-ui"
        data_source_selector.CLIENTIFY_API_TOKEN = "fake-token-para-test-app-ui"
        api_source._load_and_prepare_from_api.clear()

        # Fuente de gasto en pauta de Meta: sin estas pruebas, no tiene nada
        # que ver con Clientify — se fuerza a CSV (sin credenciales) para
        # que no dispare un fetch real a la API de Meta Ads según lo que
        # haya en el secrets.toml local de quien corra la suite.
        meta_ads_source.META_ACCESS_TOKEN = ""

        import src.auth as auth
        auth.check_password = lambda: True

        import app as real_app
        real_app.main()

    return AppTest.from_function(app)


def _no_source_app():
    def app():
        from src.ui import meta_ads_source, data_source_selector
        meta_ads_source.META_ACCESS_TOKEN = ""
        # Fuerza el default a Excel (no API) — este test es sobre el
        # placeholder de "sin fuente elegida", no sobre Clientify; sin esto,
        # el default pasaría a API (si hay un CLIENTIFY_API_TOKEN real en el
        # secrets.toml local) y dispararía un fetch real sin mock.
        data_source_selector.CLIENTIFY_API_TOKEN = ""

        import src.auth as auth
        auth.check_password = lambda: True

        import app as real_app
        real_app.main()

    return AppTest.from_function(app)


def test_marketing_e_inversion_no_bloquea_sin_fuente_clientify_elegida():
    """TAB 1 debe renderizar su contenido de Meta Ads (aunque sea el mensaje
    de "subí un archivo") SIN que se haya elegido ninguna fuente de
    contactos de Clientify — antes del fix, todo el cuerpo de la app
    (incluida esta sección, que no depende de contactos) quedaba detrás de
    un `return` temprano condicionado a `st.session_state.df`."""
    at = _no_source_app()
    at.run(timeout=15)

    assert not at.exception
    assert len(at.tabs) == 4

    tab1_info = [i.value for i in at.tabs[0].info]
    assert any("Meta Ads" in msg or "facturación" in msg.lower() for msg in tab1_info)

    # Las otras 3 pestañas SÍ dependen de contactos de Clientify -> placeholder.
    for i in (1, 2, 3):
        infos = [inf.value for inf in at.tabs[i].info]
        assert any("Elegí una fuente" in msg for msg in infos)


def test_segmentacion_clave_no_reporta_columnas_faltantes_con_fuente_api():
    """Regresión del mapeo de las 30 columnas: con la fuente API (fake
    client, esquema completo) ninguna sección de "Segmentación Clave" debe
    mostrar "La columna 'X' no existe en los datos cargados"."""
    at = _build_app_with_fake_api_client()
    at.run(timeout=30)
    at.radio(key="data_source_selector").set_value("Conectar con Clientify API").run(timeout=30)

    assert not at.exception

    seg_tab = at.tabs[1]
    info_msgs = [i.value for i in seg_tab.info]
    assert not any("no existe en los datos cargados" in msg for msg in info_msgs), info_msgs

    # Las 7 secciones de Segmentación Clave deberían haber producido un
    # gráfico cada una (Tipo de proceso, País, Estado/Provincia, Ciudad,
    # Sector, Rango de edad, Género).
    assert len(list(seg_tab.get("plotly_chart"))) == 7
