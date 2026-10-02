"""Test UI para `src/ui/data_source_selector.py` — selector de fuente de
datos (Excel subido vs API de Clientify).

Usa `streamlit.testing.v1.AppTest` (mismo harness que
`tests/test_funnel_ui.py`/`tests/test_pauta_vs_referidos_antiguedad_ui.py`)
porque `st.radio` necesita un ScriptRunContext real. No pega a la API real:
para el caso "con token", la clase `ClientifyAPIClient` se reemplaza por un
fake dentro del propio closure de `AppTest.from_function` (mismo patrón que
esos tests usan para inyectar datos sintéticos).
"""
import pandas as pd
from streamlit.testing.v1 import AppTest

from src.ui.data_source_selector import API_OPTION, EXCEL_OPTION


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


def _build_app():
    def app():
        from src.ui.data_source_selector import render_data_source_selector

        render_data_source_selector()

    return AppTest.from_function(app)


def test_selector_muestra_las_2_opciones_y_excel_es_el_default():
    at = _build_app()
    at.run(timeout=15)
    assert not at.exception

    radio = at.radio[0]
    assert list(radio.options) == ["Subir Excel", "Conectar con Clientify API"]
    assert radio.value == "Subir Excel"
    # Excel (default): se ve el uploader, no el botón de refresh de la API.
    assert len(at.get("file_uploader")) == 1
    assert not any("Actualizar datos" in b.label for b in at.button)


def test_elegir_api_sin_token_muestra_error_claro_no_traceback():
    def app():
        from src.ui import api_source

        api_source.CLIENTIFY_API_TOKEN = ""  # simula token no configurado

        from src.ui.data_source_selector import render_data_source_selector
        render_data_source_selector()

    at = AppTest.from_function(app)
    at.run(timeout=15)
    at.radio[0].set_value(API_OPTION).run(timeout=15)

    assert not at.exception
    assert len(at.error) == 1
    assert "CLIENTIFY_API_TOKEN" in at.error[0].value
    assert len(at.get("file_uploader")) == 0
    assert not any("Actualizar datos" in b.label for b in at.button)


def test_elegir_api_con_token_muestra_boton_actualizar_no_uploader():
    def app():
        from src.ui import api_source
        from tests.test_data_source_selector_ui import _fake_api_contact_df

        class _FakeClient:
            def __init__(self, token=None, base_url=None):
                pass

            def load(self):
                return _fake_api_contact_df()

        api_source.ClientifyAPIClient = _FakeClient
        api_source.CLIENTIFY_API_TOKEN = "fake-token-para-test-selector-ui"
        api_source._load_and_prepare_from_api.clear()

        from src.ui.data_source_selector import render_data_source_selector
        render_data_source_selector()

    at = AppTest.from_function(app)
    at.run(timeout=15)
    at.radio[0].set_value(API_OPTION).run(timeout=15)

    assert not at.exception
    assert len(at.error) == 0
    assert len(at.get("file_uploader")) == 0
    assert any("Datos cargados: API Clientify" in s.value for s in at.success)
    assert any("Actualizar datos" in b.label for b in at.button)
    assert not any("Cargar otro archivo" in b.label for b in at.button)
