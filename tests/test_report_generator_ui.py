"""Tests de `src/ui/report_generator.py` (botón "Generar reporte" de
Marketing, usando `streamlit.testing.v1.AppTest` — necesita un
ScriptRunContext real para que `st.button`/`st.selectbox`/
`st.download_button` funcionen.

Todo con mocks: ni la IA real ni matplotlib se llaman nunca acá para los
casos de UI pura — ver `tests/test_ai_provider.py`/`tests/test_pdf_report.py`
para esos adaptadores en aislamiento. El export de imágenes del PDF ya NO
depende de kaleido/Chromium (matplotlib, puro Python) — por eso ya no hay
un escenario de "fallback a HTML"; el PDF es siempre el botón principal y
el HTML (solo Marketing, única sección con figuras Plotly ya existentes)
es una descarga secundaria/opcional que se genera en el mismo click.

`render_report_generator` ahora es genérico por sección (ver
`src/reports/section_registry.py`) — estos tests ejercitan la sección
"marketing" (`key="..._marketing"`); Segmentación/Embudo/Gestión Comercial
comparten el mismo código, cubiertos en `tests/test_report_generator_sections_ui.py`.
"""
from streamlit.testing.v1 import AppTest


def _app_sin_api_key():
    import pandas as pd

    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_report_generator

    gasto_raw = pd.DataFrame([{"Fecha": "01/01/2025", "Divisa": "USD", "Importe": "1000"}])
    df_clientify = pd.DataFrame()
    ctx = ReportContext(gasto_raw=gasto_raw, billed_raw=None, df_clientify=df_clientify, year=2025, month=1, team="Todos")
    render_report_generator("marketing", ctx, periodo_label="Enero 2025")


def test_boton_deshabilitado_sin_api_key(monkeypatch):
    import src.ui.report_generator as report_generator_module

    monkeypatch.setattr(report_generator_module, "get_ai_provider", lambda: None)

    at = AppTest.from_function(_app_sin_api_key)
    at.run(timeout=30)

    assert not at.exception
    boton = at.button(key="btn_generar_reporte_marketing")
    assert boton.disabled is True
    assert any("Configura AI_API_KEY para generar el reporte" in c.value for c in at.caption)
    # Sin API key no debería ni ofrecerse el botón de probar conexión.
    assert not any(b.key == "btn_probar_conexion_ia_marketing" for b in at.button)


def _app_con_api_key():
    import pandas as pd

    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_report_generator

    gasto_raw = pd.DataFrame([
        {"Fecha": "01/01/2025", "Divisa": "USD", "Importe": "1000"},
        {"Fecha": "01/02/2025", "Divisa": "USD", "Importe": "2000"},
    ])
    df_clientify = pd.DataFrame([{
        "estado": "activo", "Canal offline": "Clientify - Facebook", "canal online": "paid social",
        "Fecha de cierre": "01/01/2025", "Fecha de segundo cierre": None,
        "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        "Cuota inicial pactada": "500", "Valor total del proceso": "5000",
    }])
    ctx = ReportContext(gasto_raw=gasto_raw, billed_raw=None, df_clientify=df_clientify, year=2025, month=1, team="Todos")
    render_report_generator("marketing", ctx, periodo_label="Enero 2025")


class _FakeProvider:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "## Qué dicen los números\nTodo bien.\n- Acción 1\n- Acción 2\n- Acción 3"


class _FakeProviderFalla:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        from src.data_sources.ai_provider import AIProviderError

        raise AIProviderError("saldo insuficiente (insufficient_quota)")


def test_boton_habilitado_con_api_key(monkeypatch):
    import src.ui.report_generator as report_generator_module

    monkeypatch.setattr(report_generator_module, "get_ai_provider", lambda: _FakeProvider())

    at = AppTest.from_function(_app_con_api_key)
    at.run(timeout=30)

    assert not at.exception
    boton = at.button(key="btn_generar_reporte_marketing")
    assert boton.disabled is False


def test_click_generar_reporte_entrega_pdf_y_html_siempre(monkeypatch):
    """El PDF (matplotlib, sin kaleido/Chromium) debe salir siempre como
    descarga principal, y el HTML interactivo (solo Marketing) queda como
    descarga secundaria/opcional en el mismo click."""
    import src.ui.report_generator as report_generator_module

    monkeypatch.setattr(report_generator_module, "get_ai_provider", lambda: _FakeProvider())

    at = AppTest.from_function(_app_con_api_key)
    at.run(timeout=30)
    at.button(key="btn_generar_reporte_marketing").click().run(timeout=60)

    assert not at.exception
    descargas = at.get("download_button")
    assert len(descargas) == 2
    etiquetas = [d.label for d in descargas]
    assert any("PDF" in e for e in etiquetas)
    assert any("HTML" in e for e in etiquetas)


def test_probar_conexion_ok_muestra_exito(monkeypatch):
    import src.ui.report_generator as report_generator_module

    monkeypatch.setattr(report_generator_module, "get_ai_provider", lambda: _FakeProvider())

    at = AppTest.from_function(_app_con_api_key)
    at.run(timeout=30)
    at.button(key="btn_probar_conexion_ia_marketing").click().run(timeout=30)

    assert not at.exception
    assert len(at.success) == 1


def test_probar_conexion_con_error_muestra_motivo_sanitizado(monkeypatch):
    """El motivo del error (sanitizado, sin la API key) debe mostrarse
    directo en la UI — nunca un mensaje genérico sin pistas."""
    import src.ui.report_generator as report_generator_module

    monkeypatch.setattr(report_generator_module, "get_ai_provider", lambda: _FakeProviderFalla())

    at = AppTest.from_function(_app_con_api_key)
    at.run(timeout=30)
    at.button(key="btn_probar_conexion_ia_marketing").click().run(timeout=30)

    assert not at.exception
    assert len(at.error) == 1
    assert "insufficient_quota" in at.error[0].value


def test_click_generar_reporte_con_ia_fallando_avisa_con_motivo(monkeypatch):
    """Si la IA falla para alguna sección, el reporte debe generarse igual
    (nunca se aborta) pero la UI debe avisar CUÁL sección falló — nunca un
    "no disponible" silencioso."""
    import src.ui.report_generator as report_generator_module

    monkeypatch.setattr(report_generator_module, "get_ai_provider", lambda: _FakeProviderFalla())

    at = AppTest.from_function(_app_con_api_key)
    at.run(timeout=30)
    at.button(key="btn_generar_reporte_marketing").click().run(timeout=60)

    assert not at.exception
    assert any("no se pudo generar" in w.value.lower() for w in at.warning)
    descargas = at.get("download_button")
    assert len(descargas) == 2
