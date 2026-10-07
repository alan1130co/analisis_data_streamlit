"""Tests de CAMBIO 2: cambiar Año/Mes en una gráfica de "Marketing e
Inversión" no debe volver a disparar la carga de datos (API de Meta,
Clientify, CSV) ni mostrar un spinner global — solo debe re-ejecutar el
fragmento de esa gráfica.

Nota sobre el alcance real de estos tests: `streamlit.testing.v1.AppTest`
SIEMPRE re-ejecuta el script completo en cada `.run()` (confirmado
empíricamente — no simula el rerun-solo-del-fragmento que sí ocurre en un
servidor real de Streamlit; ver docstring de
`test_cambiar_anio_no_vuelve_a_llamar_fetch_meta_ad_spend` más abajo para el
detalle). Por eso estos tests verifican 2 cosas, cada una por su cuenta
suficiente para la garantía que pide la tarea:
  1. Estático: cada función con selectores Año/Mes está decorada con
     `@st.fragment` en el código fuente (para que, en un servidor real, el
     rerun quede scopeado a esa función).
  2. Dinámico: la función de carga REAL (la que hace la llamada de red,
     envuelta en `@st.cache_data`) no se vuelve a ejecutar cuando se cambia
     el selector — gracias al cache, incluso con AppTest re-ejecutando todo
     el script, la llamada de red/parseo real no se repite.
"""
import inspect

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

_FRAGMENT_TARGETS = [
    ("src.ui.sections.ad_spend", "_render_chart"),
    ("src.ui.sections.ad_spend_billed", "_render_billed_chart"),
    ("src.ui.sections.ad_spend_cost_per_lead", "render_ad_spend_cost_per_lead"),
    ("src.ui.sections.ad_spend_roas", "render_ad_spend_roas"),
    ("src.ui.sections.ad_spend_total_roas", "render_ad_spend_total_roas"),
    ("src.ui.sections.ad_spend_vs_closures", "render_ad_spend_vs_closures"),
    ("src.ui.sections.ad_spend_vs_process_value", "render_ad_spend_vs_process_value"),
    ("src.ui.sections.ad_spend_vs_process_value_roas", "render_ad_spend_vs_process_value_roas"),
    ("src.ui.sections.ad_spend_vs_revenue", "render_ad_spend_vs_revenue"),
]


@pytest.mark.parametrize("module_path,func_name", _FRAGMENT_TARGETS)
def test_funcion_con_selectores_esta_decorada_con_st_fragment(module_path, func_name):
    """Chequeo estático: la línea `@st.fragment` debe preceder inmediatamente
    al `def` de cada función que renderiza los selectores Año/Mes + el
    gráfico — así, en un servidor real (no en `AppTest`, que no simula el
    scoping de reruns), cambiar el selector solo reejecuta esa función."""
    import importlib

    module = importlib.import_module(module_path)
    func = getattr(module, func_name)
    source_lines = inspect.getsource(module).splitlines()
    def_line_idx = next(i for i, line in enumerate(source_lines) if line.startswith(f"def {func_name}("))
    # La línea inmediatamente anterior al `def` (ignorando líneas en blanco)
    # debe ser el decorador.
    prev_idx = def_line_idx - 1
    while prev_idx >= 0 and not source_lines[prev_idx].strip():
        prev_idx -= 1
    assert source_lines[prev_idx].strip() == "@st.fragment", (
        f"{module_path}.{func_name} no está decorada con @st.fragment "
        f"(línea anterior al def: {source_lines[prev_idx]!r})"
    )


def test_cambiar_anio_no_vuelve_a_llamar_fetch_meta_ad_spend(monkeypatch):
    """Cambiar el selector "Año" de "Gasto en pauta publicitaria" (fuente
    API) no debe volver a invocar `fetch_meta_ad_spend` (la función real que
    pagina las 3 cuentas por HTTP) — `_cached_fetch_meta_ad_spend` (`@st.
    cache_data(ttl=900)`) debe devolver el resultado cacheado.

    `AppTest` re-ejecuta `app()` completo en cada `.run()` (confirmado
    empíricamente con un experimento aislado: un contador incrementado
    fuera de un fragment SÍ sube de 1 a 2 al interactuar con un selector
    DENTRO del fragment) — así que este test no prueba que Streamlit evite
    re-ejecutar el cuerpo de `render_meta_ads_source()`, sino la garantía
    real pedida por la tarea: que la llamada de red/parseo pesada
    (`fetch_meta_ad_spend`) no se repite gracias al cache, sin importar
    cuántas veces se re-ejecute el código que la envuelve."""
    from src.ui import meta_ads_source

    monkeypatch.setattr(meta_ads_source, "META_ACCESS_TOKEN", "fake-token-fragment-test")

    call_count = {"n": 0}
    fake_df = pd.DataFrame({
        "Fecha": [pd.Timestamp("2025-03-01"), pd.Timestamp("2026-03-01")],
        "Divisa": ["USD", "USD"],
        "Importe": [100.0, 200.0],
        "Año": [2025, 2026],
        "Mes_num": [3, 3],
        "Mes_Año": ["Marzo 2025", "Marzo 2026"],
    })

    def _fake_fetch(token, since, until, **kwargs):
        call_count["n"] += 1
        return fake_df, []

    monkeypatch.setattr(meta_ads_source, "fetch_meta_ad_spend", _fake_fetch)
    meta_ads_source._cached_fetch_meta_ad_spend.clear()

    def app():
        from src.ui.meta_ads_source import render_meta_ads_source
        from src.ui.sections.ad_spend import render_ad_spend_from_raw

        gasto_raw, _, _ = render_meta_ads_source()
        render_ad_spend_from_raw(gasto_raw)

    at = AppTest.from_function(app)
    at.run(timeout=20)
    assert not at.exception
    assert call_count["n"] == 1

    at.selectbox(key="anio_ad_spend").select("2025").run(timeout=20)
    assert not at.exception
    assert call_count["n"] == 1, (
        "Cambiar el selector 'Año' volvió a llamar fetch_meta_ad_spend "
        f"({call_count['n']} llamadas) — el cache_data no evitó la recarga."
    )

    at.selectbox(key="mes_ad_spend").select("Marzo").run(timeout=20)
    assert not at.exception
    assert call_count["n"] == 1


def test_cambiar_anio_no_vuelve_a_llamar_fetch_meta_billed_amount(monkeypatch):
    """Mismo chequeo que el test anterior, para "Gasto facturado por mes"
    (fuente API) y `fetch_meta_billed_amount`."""
    from src.ui.sections import ad_spend_billed

    monkeypatch.setattr(ad_spend_billed, "META_ACCESS_TOKEN", "fake-token-fragment-test-billed")

    call_count = {"n": 0}
    fake_df = pd.DataFrame({
        "Fecha": [pd.Timestamp("2025-08-01"), pd.Timestamp("2026-08-01")],
        "Divisa": ["USD", "USD"],
        "Importe": [900.0, 4589.12],
        "Año": [2025, 2026],
        "Mes_num": [8, 8],
        "Mes_Año": ["Agosto 2025", "Agosto 2026"],
    })

    def _fake_fetch(token, since, until, **kwargs):
        call_count["n"] += 1
        return fake_df, []

    monkeypatch.setattr(ad_spend_billed, "fetch_meta_billed_amount", _fake_fetch)
    ad_spend_billed._cached_fetch_meta_billed_amount.clear()

    def app():
        from src.ui.sections.ad_spend_billed import render_ad_spend_billed, API_MODE
        render_ad_spend_billed(API_MODE)

    at = AppTest.from_function(app)
    at.run(timeout=20)
    assert not at.exception
    assert call_count["n"] == 1

    at.selectbox(key="anio_ad_spend_billed").select("2025").run(timeout=20)
    assert not at.exception
    assert call_count["n"] == 1, (
        "Cambiar el selector 'Año' volvió a llamar fetch_meta_billed_amount "
        f"({call_count['n']} llamadas) — el cache_data no evitó la recarga."
    )


def test_cambiar_anio_en_grafica_de_meta_no_refetchea_clientify(monkeypatch):
    """Cambiar el selector "Año" de una gráfica de Meta Ads no debe volver a
    invocar `ClientifyAPIClient.load()` — complementa el test ya existente
    en `test_ad_spend_clientify_isolation_ui.py` (que cubre la gráfica CSV
    "Gasto en pauta publicitaria") verificando ahora una gráfica que SÍ
    recibe `df_clientify` (`ad_spend_vs_closures`), la fuente API de Meta, y
    el nuevo `@st.fragment`."""
    from src.ui import api_source, data_source_selector, meta_ads_source

    monkeypatch.setattr(meta_ads_source, "META_ACCESS_TOKEN", "")  # Meta en modo CSV, sin red
    monkeypatch.setattr(data_source_selector, "CLIENTIFY_API_TOKEN", "fake-token-clientify-frag-test")
    monkeypatch.setattr(api_source, "CLIENTIFY_API_TOKEN", "fake-token-clientify-frag-test")

    clientify_calls = {"n": 0}

    class _FakeClient:
        def __init__(self, token=None, base_url=None):
            pass

        def load(self):
            clientify_calls["n"] += 1
            return pd.DataFrame({
                "creado": [pd.Timestamp("2026-03-01")],
                "propietario": ["ana perdomo"],
                "canal online": ["paid social"],
                "Canal offline": ["clientify - facebook"],
                "estado": ["activo"],
                "Etiquetas": [""],
                "Origen de la pauta": ["facebook"],
                "Motivo de no cierre": [None],
                "Cantidad de cierres": [1.0],
                "Fecha de cierre": [pd.Timestamp("2026-03-05")],
                "Fecha de segundo cierre": [pd.NaT],
                "Fecha de tercer cierre": [pd.NaT],
                "Fecha de 4to cierre": [pd.NaT],
            })

    monkeypatch.setattr(api_source, "ClientifyAPIClient", _FakeClient)
    api_source._load_and_prepare_from_api.clear()

    def app():
        import pandas as pd
        from src.ui.data_source_selector import render_data_source_selector
        from src.ui.sections.ad_spend_vs_closures import render_ad_spend_vs_closures

        df, _ = render_data_source_selector()
        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "300"},
        ])
        render_ad_spend_vs_closures(gasto_raw, df if df is not None else pd.DataFrame())

    at = AppTest.from_function(app)
    at.run(timeout=20)
    assert not at.exception
    assert clientify_calls["n"] == 1

    at.selectbox(key="anio_ad_spend_vs_closures").select("2025").run(timeout=20)
    assert not at.exception
    assert clientify_calls["n"] == 1, (
        "Cambiar el selector 'Año' de una gráfica de Meta volvió a llamar "
        f"ClientifyAPIClient.load() ({clientify_calls['n']} llamadas)."
    )
