"""Tests de UI (`streamlit.testing.v1.AppTest`) de `src/ui/report_generator.py`
para:
- Las 3 secciones NUEVAS (Segmentación, Embudo, Gestión Comercial) vía
  `render_report_generator` — mismo código genérico que Marketing (ver
  `tests/test_report_generator_ui.py`), solo cambia `section_id`.
- El botón "Reporte completo" del sidebar (`render_full_report_generator`):
  genera un único PDF con las secciones disponibles, omite con nota la
  sección sin datos, y entrega el PDF por `st.download_button`.

Todo con mocks: nunca se llama a la IA real. `AppTest.from_function`
ejecuta el código de la función en un módulo aislado (no comparte el
namespace del archivo de test), así que cada `_app_*` construye sus datos
en línea en vez de llamar a un helper de módulo.
"""
from streamlit.testing.v1 import AppTest


class _FakeProvider:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "## Qué dicen los números\nTodo bien.\n- Acción 1\n- Acción 2\n- Acción 3"


_DF_CLIENTIFY_ROW = {
    "creado": "01/01/2026", "estado": "activo", "propietario": "Ana Perdomo",
    "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook", "canal online": "paid social",
    "país": "colombia", "provincia/estado 1": "atlantico", "ciudad 1": "barranquilla",
    "sector": "salud", "Tipo de proceso": "visa", "cumpleaños": "01/01/1990",
    "Campaña - pauta": "Campana1", "Publicacion por la que se contacto el cliente": "Video1",
    "Motivo de no cierre": "", "nombre": "cliente de prueba",
    "Fecha de cierre": "15/01/2026", "Fecha de segundo cierre": None,
    "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
    "Cuota inicial pactada": "500", "Valor total del proceso": "5000",
}


def _app_segmentacion():
    import pandas as pd

    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_report_generator

    df = pd.DataFrame([{
        "creado": "01/01/2026", "estado": "activo", "propietario": "Ana Perdomo",
        "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook", "canal online": "paid social",
        "país": "colombia", "provincia/estado 1": "atlantico", "ciudad 1": "barranquilla",
        "sector": "salud", "Tipo de proceso": "visa", "cumpleaños": "01/01/1990",
        "Campaña - pauta": "Campana1", "Publicacion por la que se contacto el cliente": "Video1",
        "Motivo de no cierre": "", "nombre": "cliente de prueba",
        "Fecha de cierre": "15/01/2026", "Fecha de segundo cierre": None,
        "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        "Cuota inicial pactada": "500", "Valor total del proceso": "5000",
    }])
    ctx = ReportContext(gasto_raw=None, billed_raw=None, df_clientify=df, year=2026, month=1, team="Todos")
    render_report_generator("segmentacion", ctx, periodo_label="Enero 2026")


def _app_embudo():
    import pandas as pd

    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_report_generator

    df = pd.DataFrame([{
        "creado": "01/01/2026", "estado": "activo", "propietario": "Ana Perdomo",
        "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook", "canal online": "paid social",
        "país": "colombia", "provincia/estado 1": "atlantico", "ciudad 1": "barranquilla",
        "sector": "salud", "Tipo de proceso": "visa", "cumpleaños": "01/01/1990",
        "Campaña - pauta": "Campana1", "Publicacion por la que se contacto el cliente": "Video1",
        "Motivo de no cierre": "", "nombre": "cliente de prueba",
        "Fecha de cierre": "15/01/2026", "Fecha de segundo cierre": None,
        "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        "Cuota inicial pactada": "500", "Valor total del proceso": "5000",
    }])
    ctx = ReportContext(gasto_raw=None, billed_raw=None, df_clientify=df, year=2026, month=1, team="Todos")
    render_report_generator("embudo", ctx, periodo_label="Enero 2026")


def _app_gestion_comercial():
    import pandas as pd

    from src.analytics.metrics import compute_all_metrics
    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_report_generator

    df = pd.DataFrame([{
        "creado": "01/01/2026", "estado": "activo", "propietario": "Ana Perdomo",
        "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook", "canal online": "paid social",
        "país": "colombia", "provincia/estado 1": "atlantico", "ciudad 1": "barranquilla",
        "sector": "salud", "Tipo de proceso": "visa", "cumpleaños": "01/01/1990",
        "Campaña - pauta": "Campana1", "Publicacion por la que se contacto el cliente": "Video1",
        "Motivo de no cierre": "", "nombre": "cliente de prueba",
        "Fecha de cierre": "15/01/2026", "Fecha de segundo cierre": None,
        "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        "Cuota inicial pactada": "500", "Valor total del proceso": "5000",
    }])
    metrics = compute_all_metrics(df, df)
    ctx = ReportContext(
        gasto_raw=None, billed_raw=None, df_clientify=df,
        year=2026, month=1, team="Todos", metrics=metrics, metrics_prev=metrics,
    )
    render_report_generator("gestion_comercial", ctx, periodo_label="Enero 2026")


def _app_sin_datos_clientify():
    import pandas as pd

    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_report_generator

    ctx = ReportContext(gasto_raw=None, billed_raw=None, df_clientify=pd.DataFrame(), year=2026, month=1, team="Todos")
    render_report_generator("segmentacion", ctx, periodo_label="Enero 2026")


class TestSeccionesNuevasBotonPorPestana:
    def test_segmentacion_boton_habilitado_y_entrega_pdf(self, monkeypatch):
        import src.ui.report_generator as mod

        monkeypatch.setattr(mod, "get_ai_provider", lambda: _FakeProvider())
        at = AppTest.from_function(_app_segmentacion)
        at.run(timeout=30)
        assert not at.exception
        assert at.button(key="btn_generar_reporte_segmentacion").disabled is False

        at.button(key="btn_generar_reporte_segmentacion").click().run(timeout=60)
        assert not at.exception
        descargas = at.get("download_button")
        assert len(descargas) == 1
        assert "PDF" in descargas[0].label

    def test_embudo_boton_habilitado_y_entrega_pdf(self, monkeypatch):
        import src.ui.report_generator as mod

        monkeypatch.setattr(mod, "get_ai_provider", lambda: _FakeProvider())
        at = AppTest.from_function(_app_embudo)
        at.run(timeout=30)
        at.button(key="btn_generar_reporte_embudo").click().run(timeout=60)
        assert not at.exception
        assert len(at.get("download_button")) == 1

    def test_gestion_comercial_boton_habilitado_y_entrega_pdf(self, monkeypatch):
        import src.ui.report_generator as mod

        monkeypatch.setattr(mod, "get_ai_provider", lambda: _FakeProvider())
        at = AppTest.from_function(_app_gestion_comercial)
        at.run(timeout=30)
        at.button(key="btn_generar_reporte_gestion_comercial").click().run(timeout=60)
        assert not at.exception
        assert len(at.get("download_button")) == 1

    def test_sin_datos_de_clientify_muestra_nota_y_no_el_boton(self, monkeypatch):
        import src.ui.report_generator as mod

        monkeypatch.setattr(mod, "get_ai_provider", lambda: _FakeProvider())
        at = AppTest.from_function(_app_sin_datos_clientify)
        at.run(timeout=30)
        assert not at.exception
        assert len(at.info) == 1
        assert not any(b.key == "btn_generar_reporte_segmentacion" for b in at.button)


def _app_reporte_completo_todas_las_secciones():
    import pandas as pd

    from src.analytics.metrics import compute_all_metrics
    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_full_report_generator

    df = pd.DataFrame([{
        "creado": "01/01/2026", "estado": "activo", "propietario": "Ana Perdomo",
        "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook", "canal online": "paid social",
        "país": "colombia", "provincia/estado 1": "atlantico", "ciudad 1": "barranquilla",
        "sector": "salud", "Tipo de proceso": "visa", "cumpleaños": "01/01/1990",
        "Campaña - pauta": "Campana1", "Publicacion por la que se contacto el cliente": "Video1",
        "Motivo de no cierre": "", "nombre": "cliente de prueba",
        "Fecha de cierre": "15/01/2026", "Fecha de segundo cierre": None,
        "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        "Cuota inicial pactada": "500", "Valor total del proceso": "5000",
    }])
    metrics = compute_all_metrics(df, df)
    gasto_raw = pd.DataFrame([{"Fecha": "01/01/2026", "Divisa": "USD", "Importe": "1000"}])
    ctx = ReportContext(
        gasto_raw=gasto_raw, billed_raw=None, df_clientify=df,
        year=2026, month=1, team="Todos", metrics=metrics, metrics_prev=metrics,
    )
    render_full_report_generator(ctx, periodo_label="Enero 2026")


def _app_reporte_completo_sin_gasto_pauta():
    import pandas as pd

    from src.analytics.metrics import compute_all_metrics
    from src.reports.section_types import ReportContext
    from src.ui.report_generator import render_full_report_generator

    df = pd.DataFrame([{
        "creado": "01/01/2026", "estado": "activo", "propietario": "Ana Perdomo",
        "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook", "canal online": "paid social",
        "país": "colombia", "provincia/estado 1": "atlantico", "ciudad 1": "barranquilla",
        "sector": "salud", "Tipo de proceso": "visa", "cumpleaños": "01/01/1990",
        "Campaña - pauta": "Campana1", "Publicacion por la que se contacto el cliente": "Video1",
        "Motivo de no cierre": "", "nombre": "cliente de prueba",
        "Fecha de cierre": "15/01/2026", "Fecha de segundo cierre": None,
        "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        "Cuota inicial pactada": "500", "Valor total del proceso": "5000",
    }])
    metrics = compute_all_metrics(df, df)
    ctx = ReportContext(
        gasto_raw=pd.DataFrame(), billed_raw=None, df_clientify=df,
        year=2026, month=1, team="Todos", metrics=metrics, metrics_prev=metrics,
    )
    render_full_report_generator(ctx, periodo_label="Enero 2026")


class TestReporteCompletoSidebar:
    def test_genera_un_solo_pdf_con_las_4_secciones(self, monkeypatch):
        import src.ui.report_generator as mod

        monkeypatch.setattr(mod, "get_ai_provider", lambda: _FakeProvider())
        at = AppTest.from_function(_app_reporte_completo_todas_las_secciones)
        at.run(timeout=30)
        assert not at.exception
        assert at.button(key="btn_generar_reporte_completo").disabled is False

        at.button(key="btn_generar_reporte_completo").click().run(timeout=90)
        assert not at.exception
        descargas = at.get("download_button")
        assert len(descargas) == 1
        assert "completo" in descargas[0].file_name.lower()

    def test_seccion_marketing_sin_datos_se_omite_con_aviso_y_el_resto_sigue(self, monkeypatch):
        import src.ui.report_generator as mod

        monkeypatch.setattr(mod, "get_ai_provider", lambda: _FakeProvider())
        at = AppTest.from_function(_app_reporte_completo_sin_gasto_pauta)
        at.run(timeout=30)
        # Aviso de que Marketing se omite por falta de gasto en pauta.
        assert any("Marketing" in i.value for i in at.info)

        at.button(key="btn_generar_reporte_completo").click().run(timeout=90)
        assert not at.exception
        assert len(at.get("download_button")) == 1
