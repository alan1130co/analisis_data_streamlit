"""Test UI para `src/ui/meta_ads_source.py` — selector de fuente de gasto en
pauta (API de Meta vs CSV subido). Usa `streamlit.testing.v1.AppTest` (mismo
harness que `tests/test_data_source_selector_ui.py`). No pega a la API
real: la función cacheada `_cached_fetch_meta_ad_spend` se reemplaza por un
fake dentro del propio closure de `AppTest.from_function`.
"""
import pandas as pd
from streamlit.testing.v1 import AppTest

from src.ui.meta_ads_source import API_OPTION, CSV_OPTION


def _build_app():
    def app():
        from src.ui.meta_ads_source import render_meta_ads_source
        render_meta_ads_source()

    return AppTest.from_function(app)


def test_sin_token_default_es_csv_y_muestra_uploader():
    def app():
        from src.ui import meta_ads_source
        meta_ads_source.META_ACCESS_TOKEN = ""
        meta_ads_source.render_meta_ads_source()

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    radio = at.radio(key="meta_ads_source")
    assert list(radio.options) == [API_OPTION, CSV_OPTION]
    assert radio.value == CSV_OPTION
    assert len(at.get("file_uploader")) == 1
    assert not any("Actualizar datos de Meta" in b.label for b in at.button)


def test_con_token_default_es_api_sin_uploader_y_con_boton_actualizar():
    def app():
        from src.ui import meta_ads_source

        meta_ads_source.META_ACCESS_TOKEN = "fake-token-para-test-meta-source"

        def _fake_cached_fetch(token, since, until):
            import pandas as pd
            df = pd.DataFrame({
                "Fecha": [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")],
                "Divisa": ["USD", "USD"],
                "Importe": [10.0, 20.0],
                "Año": [2026, 2026],
                "Mes_num": [1, 1],
                "Mes_Año": ["Enero 2026", "Enero 2026"],
            })
            return df, [], "2026-01-02 10:00:00"

        meta_ads_source._cached_fetch_meta_ad_spend = _fake_cached_fetch
        meta_ads_source.render_meta_ads_source()

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    radio = at.radio(key="meta_ads_source")
    assert radio.value == API_OPTION
    assert len(at.get("file_uploader")) == 0
    assert any("Actualizar datos de Meta" in b.label for b in at.button)
    captions = [c.value for c in at.caption]
    assert any("2026-01-01" in c and "2026-01-02" in c for c in captions)
    assert any("2026-01-02 10:00:00" in c for c in captions)


def test_con_token_pero_cuenta_fallida_muestra_warning_sin_tumbar_la_app():
    def app():
        from src.ui import meta_ads_source

        meta_ads_source.META_ACCESS_TOKEN = "fake-token-para-test-meta-source-warning"

        def _fake_cached_fetch(token, since, until):
            import pandas as pd
            df = pd.DataFrame({
                "Fecha": [pd.Timestamp("2026-01-01")],
                "Divisa": ["USD"],
                "Importe": [10.0],
                "Año": [2026],
                "Mes_num": [1],
                "Mes_Año": ["Enero 2026"],
            })
            return df, ["Meta Ads — cuenta 'Contingencia': 403 sin permiso"], "2026-01-02 10:00:00"

        meta_ads_source._cached_fetch_meta_ad_spend = _fake_cached_fetch
        meta_ads_source.render_meta_ads_source()

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    assert any("Contingencia" in w.value for w in at.warning)


def test_sin_token_eligiendo_api_muestra_error_claro_no_traceback():
    def app():
        from src.ui import meta_ads_source
        meta_ads_source.META_ACCESS_TOKEN = ""
        meta_ads_source.render_meta_ads_source()

    at = AppTest.from_function(app)
    at.run(timeout=15)
    at.radio(key="meta_ads_source").set_value(API_OPTION).run(timeout=15)

    assert not at.exception
    assert len(at.error) == 1
    assert "META_ACCESS_TOKEN" in at.error[0].value
    assert len(at.get("file_uploader")) == 0


def test_boton_actualizar_llama_a_clear_meta_api_cache():
    """El botón "Actualizar datos de Meta" debe invocar `clear_meta_api_cache()`
    (que limpia el `st.cache_data` real) antes de `st.rerun()` — se verifica
    reemplazando esa función por un contador en vez de ejercitar el cache
    real de Streamlit (más robusto dentro de `AppTest`)."""
    def app():
        from src.ui import meta_ads_source
        import streamlit as st

        meta_ads_source.META_ACCESS_TOKEN = "fake-token-boton-actualizar"

        def _fake_cached_fetch(token, since, until):
            import pandas as pd
            df = pd.DataFrame({
                "Fecha": [pd.Timestamp("2026-01-01")],
                "Divisa": ["USD"],
                "Importe": [10.0],
                "Año": [2026],
                "Mes_num": [1],
                "Mes_Año": ["Enero 2026"],
            })
            return df, [], "t"

        if "clear_calls" not in st.session_state:
            st.session_state.clear_calls = 0

        def _fake_clear():
            st.session_state.clear_calls += 1

        meta_ads_source._cached_fetch_meta_ad_spend = _fake_cached_fetch
        meta_ads_source.clear_meta_api_cache = _fake_clear
        meta_ads_source.render_meta_ads_source()

    at = AppTest.from_function(app)
    at.run(timeout=15)
    assert not at.exception
    assert at.session_state["clear_calls"] == 0

    buttons = [b for b in at.button if "Actualizar datos de Meta" in b.label]
    assert len(buttons) == 1
    buttons[0].click().run(timeout=15)

    assert not at.exception
    assert at.session_state["clear_calls"] == 1
