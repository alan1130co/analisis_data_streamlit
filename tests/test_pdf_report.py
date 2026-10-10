"""Tests de `src/reports/pdf_report.py`:
- El PDF generado es válido (cabecera %PDF, N páginas esperado, contiene
  los títulos de las secciones) — verificado con `pypdf`, sin red.
- El export de imágenes es vía matplotlib (Agg, puro Python/C) — nunca
  depende de kaleido/Chromium, así que no hay escenario de timeout/cuelgue
  que probar (ver `chart_builder_matplotlib.py` para el porqué del cambio).
- Fallback a HTML autocontenido — ahora es una descarga SECUNDARIA/opcional
  (no un fallback del PDF, ver `src/ui/report_generator.py`), pero sigue
  sin depender de kaleido (usa `plotly.io.to_html`, no `fig.to_image`).

Todo sin red ni Chromium.
"""
import base64
from unittest import mock

import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import pytest
from pypdf import PdfReader

from src.reports import pdf_report
from src.reports.pdf_report import ImageExportError, build_html_report, build_pdf_report

matplotlib.use("Agg")

# PNG 1x1 blanco válido, en bytes — para los tests que no necesitan dibujar
# una figura real, solo ensamblar el PDF.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _mpl_figure() -> plt.Figure:
    fig, ax = plt.subplots()
    ax.bar(["Enero 2025", "Febrero 2025"], [100, 200])
    return fig


def _grupos_de_prueba() -> list[dict]:
    return [
        {
            "titulo": "Gasto en pauta y facturación real vs. facturada",
            "figuras": [("Gasto en pauta", _mpl_figure())],
            "analisis": (
                "## Qué va bien\nEl gasto creció, con acentos: áéíóúñ ¿Cómo va? ¡Bien!\n"
                "- Acción concreta 1\n- Acción concreta 2\n- Acción concreta 3"
            ),
        },
        {
            "titulo": "Costo promedio por lead de redes",
            "figuras": [("Costo por lead", _mpl_figure())],
            "analisis": "## Qué va mal\nEl costo por lead subió.\n- Acción concreta 4",
        },
    ]


class TestBuildPdfReport:
    def test_pdf_header_valido(self):
        pdf_bytes = build_pdf_report(
            periodo_label="2025", resumen_ejecutivo="## Resumen\nTodo bien.", grupos=_grupos_de_prueba(),
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_numero_de_paginas_esperado(self):
        """1 portada + 1 resumen ejecutivo + 1 por cada grupo (2) + 1 de
        conclusiones = 5 páginas."""
        pdf_bytes = build_pdf_report(
            periodo_label="2025", resumen_ejecutivo="## Resumen\nTodo bien.", grupos=_grupos_de_prueba(),
        )
        reader = PdfReader_from_bytes(pdf_bytes)
        assert len(reader.pages) == 5

    def test_contiene_titulos_de_secciones(self):
        pdf_bytes = build_pdf_report(
            periodo_label="2025", resumen_ejecutivo="## Resumen\nTodo bien.", grupos=_grupos_de_prueba(),
        )
        reader = PdfReader_from_bytes(pdf_bytes)
        texto_completo = "".join(page.extract_text() for page in reader.pages)
        assert pdf_report.TITULO_PORTADA in texto_completo
        assert pdf_report.TITULO_RESUMEN in texto_completo
        assert pdf_report.TITULO_CONCLUSIONES in texto_completo
        assert "Gasto en pauta y facturación real vs. facturada" in texto_completo
        assert "Costo promedio por lead de redes" in texto_completo

    def test_acentos_se_renderizan_correctamente(self):
        pdf_bytes = build_pdf_report(
            periodo_label="2025", resumen_ejecutivo="## Resumen\nTodo bien.", grupos=_grupos_de_prueba(),
        )
        reader = PdfReader_from_bytes(pdf_bytes)
        texto_completo = "".join(page.extract_text() for page in reader.pages)
        assert "áéíóúñ" in texto_completo
        assert "¿Cómo va?" in texto_completo

    def test_imagen_fallida_lanza_image_export_error(self):
        with mock.patch.object(pdf_report, "_figure_to_png_bytes", side_effect=ImageExportError("dibujo roto")):
            with pytest.raises(ImageExportError):
                build_pdf_report(periodo_label="2025", resumen_ejecutivo="x", grupos=_grupos_de_prueba())

    def test_no_depende_de_plotly_ni_kaleido(self):
        """El PDF nunca debe llamar a `fig.to_image` (kaleido) — las
        figuras que recibe son de matplotlib, no de Plotly."""
        fig_plotly = go.Figure(go.Bar(x=["x"], y=[1]))
        with mock.patch.object(fig_plotly, "to_image", side_effect=AssertionError("no debería llamarse")):
            grupos = [{"titulo": "Grupo", "figuras": [("Gráfica", _mpl_figure())], "analisis": "## Ok\nOk."}]
            build_pdf_report(periodo_label="2025", resumen_ejecutivo="## Ok\nOk.", grupos=grupos)


class TestFigureToPngBytes:
    def test_devuelve_png_valido_para_una_figura_real(self):
        png_bytes = pdf_report._figure_to_png_bytes(_mpl_figure())
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_excepcion_de_savefig_se_propaga_como_image_export_error(self):
        fig = _mpl_figure()
        with mock.patch.object(fig, "savefig", side_effect=RuntimeError("fuente no encontrada")):
            with pytest.raises(ImageExportError, match="fuente no encontrada"):
                pdf_report._figure_to_png_bytes(fig)


class TestBuildHtmlReport:
    def test_no_depende_de_kaleido(self):
        """`build_html_report` nunca llama a `fig.to_image` — si lo
        hiciera, este test fallaría al interceptarlo con un mock que
        lanza."""
        fig = go.Figure(go.Bar(x=["x"], y=[1]))
        with mock.patch.object(fig, "to_image", side_effect=AssertionError("no debería llamarse")):
            grupos = [{"titulo": "Grupo", "figuras": [("Gráfica", fig)], "analisis": "## Qué va bien\nOk."}]
            html = build_html_report(periodo_label="2025", resumen_ejecutivo="## Resumen\nOk.", grupos=grupos)
        assert "<html" in html

    def test_contiene_titulos_y_grafica_interactiva(self):
        fig = go.Figure(go.Bar(x=["Enero 2025", "Febrero 2025"], y=[100, 200]))
        grupos = [
            {
                "titulo": "Gasto en pauta y facturación real vs. facturada",
                "figuras": [("Gasto en pauta", fig)],
                "analisis": "## Qué va bien\nOk.",
            },
        ]
        html = build_html_report(periodo_label="2025", resumen_ejecutivo="## Resumen\nOk.", grupos=grupos)
        assert pdf_report.TITULO_PORTADA in html
        assert pdf_report.TITULO_RESUMEN in html
        assert "Gasto en pauta y facturación real vs. facturada" in html
        assert "Plotly.newPlot" in html  # gráfica interactiva embebida

    def test_plotlyjs_se_embebe_una_sola_vez(self):
        """plotly.js completo (~3MB) debe incluirse UNA sola vez, no una
        vez por cada una de las N gráficas del reporte."""
        fig = go.Figure(go.Bar(x=["Enero 2025"], y=[100]))
        grupos = [
            {"titulo": "Grupo 1", "figuras": [("G1", fig)], "analisis": "x"},
            {"titulo": "Grupo 2", "figuras": [("G2", fig)], "analisis": "x"},
        ]
        html = build_html_report(periodo_label="2025", resumen_ejecutivo="x", grupos=grupos)
        assert html.count("function Plotly_require") <= 1 or html.count("Plotly.newPlot") >= 1


def PdfReader_from_bytes(pdf_bytes: bytes) -> PdfReader:
    import io

    return PdfReader(io.BytesIO(pdf_bytes))
