"""Tests de `src/reports/pdf_report.py::build_full_pdf_report` — el PDF del
"Reporte completo" (todas las secciones en un solo documento, con portada
e índice al inicio). Complementa `tests/test_pdf_report.py` (que cubre
`build_pdf_report`/`build_html_report`, sin cambios de comportamiento para
una sola sección)."""
import io

import matplotlib
import matplotlib.pyplot as plt
from pypdf import PdfReader

from src.reports import pdf_report
from src.reports.pdf_report import build_full_pdf_report

matplotlib.use("Agg")


def _mpl_figure():
    fig, ax = plt.subplots()
    ax.bar(["Enero 2026", "Febrero 2026"], [10, 20])
    return fig


def _secciones_completas() -> list[dict]:
    return [
        {
            "titulo": "Marketing e Inversión",
            "grupos": [{"titulo": "Gasto y facturado", "figuras": [("Gasto", _mpl_figure())], "analisis": "## Qué dicen los números\nOk."}],
        },
        {
            "titulo": "Segmentación Clave",
            "grupos": [{"titulo": "Geografía", "figuras": [("Países", _mpl_figure())], "analisis": "## Qué dicen los números\nOk."}],
        },
        {"titulo": "Embudo y Canales", "sin_datos": True, "nota_sin_datos": "No hay datos de Clientify cargados."},
        {
            "titulo": "Gestión Comercial",
            "grupos": [{"titulo": "KPIs del mes", "figuras": [], "analisis": "## Conclusión\nOk."}],
        },
    ]


class TestBuildFullPdfReport:
    def test_pdf_header_valido(self):
        pdf_bytes = build_full_pdf_report(
            periodo_label="2026", resumen_ejecutivo_global="## Resumen ejecutivo global\nOk.", secciones=_secciones_completas(),
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_contiene_portada_indice_y_las_4_secciones(self):
        pdf_bytes = build_full_pdf_report(
            periodo_label="2026", resumen_ejecutivo_global="## Resumen ejecutivo global\nOk.\n## Top 5 prioridades\n- P1",
            secciones=_secciones_completas(),
        )
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto = "".join(p.extract_text() for p in reader.pages)

        assert pdf_report.TITULO_PORTADA_COMPLETO in texto
        assert pdf_report.TITULO_INDICE in texto
        assert "Marketing e Inversión" in texto
        assert "Segmentación Clave" in texto
        assert "Embudo y Canales" in texto
        assert "Gestión Comercial" in texto

    def test_seccion_sin_datos_se_omite_con_nota_sin_romper_el_resto(self):
        pdf_bytes = build_full_pdf_report(
            periodo_label="2026", resumen_ejecutivo_global="## Resumen ejecutivo global\nOk.", secciones=_secciones_completas(),
        )
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto = "".join(p.extract_text() for p in reader.pages)

        assert "No hay datos de Clientify cargados." in texto
        # Las demás secciones (antes y después de la omitida) siguen presentes.
        assert "Gestión Comercial" in texto
        assert "KPIs del mes" in texto

    def test_indice_marca_la_seccion_sin_datos_como_omitida(self):
        pdf_bytes = build_full_pdf_report(
            periodo_label="2026", resumen_ejecutivo_global="x", secciones=_secciones_completas(),
        )
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto = "".join(p.extract_text() for p in reader.pages)
        assert "omitida" in texto.lower()

    def test_no_depende_de_kaleido(self):
        """Las imágenes vienen de matplotlib (ver `_mpl_figure`) — nunca se
        exportan vía Plotly+kaleido."""
        import plotly.graph_objects as go
        from unittest import mock

        fig_plotly = go.Figure(go.Bar(x=["x"], y=[1]))
        with mock.patch.object(fig_plotly, "to_image", side_effect=AssertionError("no debería llamarse")):
            build_full_pdf_report(periodo_label="2026", resumen_ejecutivo_global="x", secciones=_secciones_completas())
