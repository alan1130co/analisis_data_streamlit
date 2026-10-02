"""Investigación/regresión: el selector Año/Mes de "Gasto en pauta
publicitaria (Meta Ads)" (primera gráfica de TAB 1, `src/ui/sections/
ad_spend.py`) no debe disparar ningún fetch a la API de Clientify — esa
gráfica solo depende del archivo de Meta Ads subido, nunca de `df_clientify`.

Usa `streamlit.testing.v1.AppTest` (mismo harness que `test_app_ui.py`),
pero a diferencia de esos tests NO limpia `_load_and_prepare_from_api` en
cada rerun — automatizar esa limpieza en cada `.run()` (como hacen los tests
existentes, para aislarse entre tests) enmascararía justo el comportamiento
que se quiere medir acá: cuántas veces se invoca `ClientifyAPIClient.load()`
a través de varios reruns consecutivos.
"""
import inspect

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.ui import api_source

_fake_client_calls = {"count": 0}
_cache_cleared = {"done": False}


def _fake_api_contact_df() -> pd.DataFrame:
    return pd.DataFrame({
        "creado": [pd.Timestamp("2026-01-01")],
        "propietario": ["ana perdomo"],
        "canal online": ["paid social"],
        "Canal offline": ["clientify - whatsapp"],
        "estado": ["sin definir (api)"],
        "Etiquetas": [""],
        "Origen de la pauta": [None],
        "Motivo de no cierre": [None],
        "Cantidad de cierres": [0.0],
        "Fecha de cierre": [pd.NaT],
        "Fecha de segundo cierre": [pd.NaT],
        "Fecha de tercer cierre": [pd.NaT],
        "Fecha de 4to cierre": [pd.NaT],
        "Valor total del proceso": [0.0],
        "Valor total segundo cierre": [0.0],
        "Valor total tercer cierre": [0.0],
        "Valor total 4to cierre": [0.0],
        "Cuota inicial pactada": [0.0],
        "Cuota inicial segundo cierre": [0.0],
        "Cuota inicial tercer cierre": [0.0],
        "Cuota inicial 4to cierre": [0.0],
    })


_AD_SPEND_CSV = (
    "Fecha,Divisa,Importe,Identificador de la transaccion\n"
    "01/01/2026,USD,100.00,TX1\n"
    "01/02/2026,USD,200.00,TX2\n"
    "01/03/2026,USD,300.00,TX3\n"
).encode("utf-8")


def _app():
    from src.ui import api_source
    from tests.test_ad_spend_clientify_isolation_ui import _fake_client_calls, _cache_cleared, _fake_api_contact_df

    class _FakeClient:
        def __init__(self, token=None, base_url=None):
            pass

        def load(self):
            _fake_client_calls["count"] += 1
            return _fake_api_contact_df()

    api_source.ClientifyAPIClient = _FakeClient
    api_source.CLIENTIFY_API_TOKEN = "fake-token-bug-a-isolation"
    if not _cache_cleared["done"]:
        api_source._load_and_prepare_from_api.clear()
        _cache_cleared["done"] = True

    import src.auth as auth
    auth.check_password = lambda: True

    import app as real_app
    real_app.main()


def test_cambiar_selector_de_gasto_en_pauta_no_refetchea_clientify():
    """Reproduce el reporte del usuario: elegir la fuente API, cargar un
    archivo de Meta Ads, y cambiar el selector Año/Mes de la PRIMERA gráfica
    de TAB 1 ("Gasto en pauta publicitaria"). `ClientifyAPIClient.load()`
    debe invocarse una única vez (la carga inicial) — ninguna interacción
    con ese selector debe sumar una invocación más."""
    _fake_client_calls["count"] = 0
    _cache_cleared["done"] = False

    at = AppTest.from_function(_app)
    at.run(timeout=30)

    # Subir el archivo de Meta Ads y elegir la fuente API.
    at.get("file_uploader")[0].upload("meta_ads.csv", _AD_SPEND_CSV, "text/csv").run(timeout=30)
    at.radio[0].set_value("Conectar con Clientify API").run(timeout=30)

    assert not at.exception
    assert _fake_client_calls["count"] == 1, (
        f"Se esperaba 1 sola llamada a ClientifyAPIClient.load() tras la carga "
        f"inicial, hubo {_fake_client_calls['count']}"
    )

    # Cambiar el selector "Mes" de la gráfica de Meta Ads (key="mes_ad_spend")
    # — esta gráfica NO depende de ningún contacto de Clientify.
    at.selectbox(key="mes_ad_spend").set_value("Febrero").run(timeout=30)

    assert not at.exception
    assert _fake_client_calls["count"] == 1, (
        f"Cambiar el selector de 'Gasto en pauta publicitaria' no debería "
        f"tocar la fuente de Clientify — hubo {_fake_client_calls['count']} "
        f"llamadas a ClientifyAPIClient.load() en total (se esperaba 1)"
    )

    # Idem para el selector "Año" (key="anio_ad_spend").
    at.selectbox(key="anio_ad_spend").set_value(2026).run(timeout=30)

    assert not at.exception
    assert _fake_client_calls["count"] == 1, (
        f"Cambiar el selector 'Año' de 'Gasto en pauta publicitaria' no debería "
        f"tocar la fuente de Clientify — hubo {_fake_client_calls['count']} "
        f"llamadas a ClientifyAPIClient.load() en total (se esperaba 1)"
    )


def test_spinner_de_sync_solo_depende_del_cache_data_no_de_un_wrapper_manual():
    """Regresión específica del bug: `render_api_source` tenía un
    `with st.spinner(...):` manual envolviendo la llamada a
    `_load_and_prepare_from_api` — eso hacía aparecer el spinner de "
    "Descargando contactos..." en CUALQUIER rerun de Streamlit (cache HIT o
    MISS), incluido al cambiar un selector que no toca Clientify para nada.

    El fix correcto es dejar que `show_spinner` del propio decorador
    `st.cache_data` controle el mensaje — Streamlit solo lo muestra mientras
    el cuerpo de la función se ejecuta de verdad (un MISS real)."""
    source = inspect.getsource(api_source.render_api_source)
    assert "st.spinner" not in source, (
        "render_api_source no debe envolver la llamada cacheada en un "
        "`with st.spinner(...)` manual — eso muestra el spinner en TODO "
        "rerun, incluso en un cache HIT. El mensaje debe vivir en el "
        "`show_spinner=` del decorador @st.cache_data de "
        "_load_and_prepare_from_api."
    )

    show_spinner = api_source._load_and_prepare_from_api._info.show_spinner
    assert isinstance(show_spinner, str) and show_spinner, (
        "El decorador @st.cache_data de _load_and_prepare_from_api debe tener "
        "show_spinner con un mensaje descriptivo (no False, no vacío) — así "
        "Streamlit lo muestra únicamente durante un MISS real, nunca en un HIT."
    )
