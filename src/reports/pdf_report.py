"""Render del PDF del reporte de Marketing e Inversión — portada, resumen
ejecutivo, cada gráfica como imagen con su análisis debajo, y conclusiones/
plan de acción al final.

Imágenes vía matplotlib (`src/reports/chart_builder_matplotlib.py`), NO
Plotly+kaleido: kaleido depende de un Chromium embebido que, confirmado en
desarrollo (Windows, entorno local del usuario), puede quedarse esperando
indefinidamente a que ese Chromium arranque, sin lanzar ninguna excepción
— el PDF nunca salía, siempre caía al fallback HTML. matplotlib (backend
"Agg", ver `chart_builder_matplotlib.py`) es una dependencia pura de pip,
sin proceso externo ni navegador, así que no tiene ese modo de falla: el
PDF con gráficas ahora sale siempre, en cualquier entorno (Windows local o
Streamlit Cloud). PDF con reportlab (Platypus) — las letras base14
(Helvetica) de reportlab usan WinAnsiEncoding por defecto, que ya cubre los
caracteres acentuados del español (á é í ó ú ñ ¿ ¡), sin necesidad de
embeber una fuente TTF aparte.

El reporte HTML interactivo (`build_html_report`, con las figuras de
Plotly) se conserva como descarga SECUNDARIA/opcional (ver
`src/ui/report_generator.py`) — ya NO es un fallback del PDF, es un
complemento para quien quiera interactividad.
"""
from __future__ import annotations

import io
from datetime import date

import plotly.graph_objects as go
import plotly.io as pio
from matplotlib.figure import Figure as MplFigure
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

IMAGE_WIDTH_PX = 1100
IMAGE_HEIGHT_PX = 620
_IMAGE_DOC_WIDTH_CM = 16.0
_IMAGE_DOC_HEIGHT_CM = _IMAGE_DOC_WIDTH_CM * IMAGE_HEIGHT_PX / IMAGE_WIDTH_PX

TITULO_PORTADA = "Reporte de Marketing e Inversión"
TITULO_RESUMEN = "Resumen ejecutivo"
TITULO_CONCLUSIONES = "Conclusiones y plan de acción"


class ImageExportError(Exception):
    """El export de una figura a PNG falló (no debería ocurrir con
    matplotlib — ver nota de módulo; se conserva para que un error
    inesperado de dibujo no rompa el reporte sin una causa clara)."""


def _figure_to_png_bytes(fig: MplFigure) -> bytes:
    """Exporta una figura de matplotlib a PNG en memoria. A diferencia del
    `fig.to_image()` de Plotly+kaleido, esto es puro Python/C (sin proceso
    externo) — no puede "colgarse" esperando un navegador."""
    buffer = io.BytesIO()
    try:
        fig.savefig(buffer, format="png", bbox_inches="tight")
    except Exception as exc:
        raise ImageExportError(str(exc)) from exc
    finally:
        import matplotlib.pyplot as plt

        plt.close(fig)
    return buffer.getvalue()


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "titulo_portada": ParagraphStyle(
            "TituloPortada", parent=base["Title"], fontSize=26, alignment=TA_CENTER, spaceAfter=18,
        ),
        "subtitulo_portada": ParagraphStyle(
            "SubtituloPortada", parent=base["Normal"], fontSize=14, alignment=TA_CENTER,
            spaceAfter=8, textColor=colors.HexColor("#444444"),
        ),
        "h1": ParagraphStyle("H1Reporte", parent=base["Heading1"], fontSize=18, spaceBefore=12, spaceAfter=10),
        "h2": ParagraphStyle(
            "H2Reporte", parent=base["Heading2"], fontSize=14, spaceBefore=10, spaceAfter=6,
            textColor=colors.HexColor("#1F2937"),
        ),
        "cuerpo": ParagraphStyle("CuerpoReporte", parent=base["Normal"], fontSize=10.5, leading=15, alignment=TA_LEFT, spaceAfter=6),
    }


def _markdown_lite_to_flowables(texto: str, estilos: dict) -> list:
    """Convierte el texto del análisis de IA (Markdown simple: "## " para
    subtítulos de sección, "- "/"* " para viñetas, el resto párrafo normal)
    a flowables de reportlab. La IA siempre devuelve este formato exacto
    (ver `src/config/report_prompts.py::SECTION_INSTRUCTIONS`) — no hace
    falta un parser de Markdown completo."""
    flowables = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("## "):
            flowables.append(Paragraph(linea[3:].strip(), estilos["h2"]))
        elif linea.startswith("- ") or linea.startswith("* "):
            flowables.append(Paragraph(f"• {linea[2:].strip()}", estilos["cuerpo"]))
        else:
            flowables.append(Paragraph(linea, estilos["cuerpo"]))
    return flowables


def _markdown_lite_to_html(texto: str) -> str:
    partes = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("## "):
            partes.append(f"<h3>{linea[3:].strip()}</h3>")
        elif linea.startswith("- ") or linea.startswith("* "):
            partes.append(f"<li>{linea[2:].strip()}</li>")
        else:
            partes.append(f"<p>{linea}</p>")
    return "".join(partes)


def build_pdf_report(
    *,
    periodo_label: str,
    resumen_ejecutivo: str,
    grupos: list[dict],
    fecha_generacion: date | None = None,
    titulo_portada: str | None = None,
) -> bytes:
    """Genera el PDF de UNA sección en memoria y devuelve los bytes.

    `grupos`: lista de `{"titulo": str, "figuras": [(titulo_grafica,
    matplotlib.figure.Figure), ...], "analisis": str}` — un elemento por
    grupo lógico de gráficas de esa sección (ver `src/reports/
    section_registry.py`). `titulo_portada`: título de tapa — por defecto
    `TITULO_PORTADA` (Marketing, para no romper los llamadores existentes);
    las demás secciones pasan el suyo (p.ej. "Reporte de Segmentación Clave").

    Lanza `ImageExportError` si el dibujo de alguna figura falla (no
    debería ocurrir en condiciones normales — ver nota de módulo).
    """
    fecha_generacion = fecha_generacion or date.today()
    titulo_portada = titulo_portada or TITULO_PORTADA
    estilos = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )

    story: list = []

    # --- Portada ---
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph(titulo_portada, estilos["titulo_portada"]))
    story.append(Paragraph(f"Período analizado: {periodo_label}", estilos["subtitulo_portada"]))
    story.append(Paragraph(f"Generado el {fecha_generacion.strftime('%d/%m/%Y')}", estilos["subtitulo_portada"]))
    story.append(PageBreak())

    # --- Resumen ejecutivo ---
    story.append(Paragraph(TITULO_RESUMEN, estilos["h1"]))
    story.extend(_markdown_lite_to_flowables(resumen_ejecutivo, estilos))
    story.append(PageBreak())

    # --- Grupos: gráficas + análisis ---
    for grupo in grupos:
        story.append(Paragraph(grupo["titulo"], estilos["h1"]))
        for titulo_grafica, fig in grupo["figuras"]:
            png_bytes = _figure_to_png_bytes(fig)
            img = Image(io.BytesIO(png_bytes), width=_IMAGE_DOC_WIDTH_CM * cm, height=_IMAGE_DOC_HEIGHT_CM * cm)
            story.append(Paragraph(titulo_grafica, estilos["h2"]))
            story.append(img)
            story.append(Spacer(1, 0.3 * cm))
        story.extend(_markdown_lite_to_flowables(grupo["analisis"], estilos))
        story.append(PageBreak())

    # --- Conclusiones / plan de acción ---
    story.append(Paragraph(TITULO_CONCLUSIONES, estilos["h1"]))
    story.extend(_markdown_lite_to_flowables(resumen_ejecutivo, estilos))

    doc.build(story)
    return buffer.getvalue()


def build_html_report(
    *,
    periodo_label: str,
    resumen_ejecutivo: str,
    grupos: list[dict],
    fecha_generacion: date | None = None,
    titulo_portada: str | None = None,
) -> str:
    """Versión interactiva (Plotly) de UNA sección — descarga SECUNDARIA/
    opcional (ver `src/ui/report_generator.py`), mismo contenido que
    `build_pdf_report` pero con las gráficas interactivas
    (`plotly.io.to_html`) en vez de imágenes estáticas. plotly.js se
    embebe UNA sola vez (en la primera gráfica) para no duplicar ~3MB por
    cada gráfica del reporte."""
    fecha_generacion = fecha_generacion or date.today()
    titulo_portada = titulo_portada or TITULO_PORTADA
    partes = [
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>",
        f"<title>{titulo_portada}</title></head>"
        "<body style=\"font-family: Arial, sans-serif; max-width: 900px; margin: 2rem auto;\">",
        f"<h1>{titulo_portada}</h1>"
        f"<p>Período analizado: {periodo_label}<br>"
        f"Generado el {fecha_generacion.strftime('%d/%m/%Y')}</p>",
        f"<h2>{TITULO_RESUMEN}</h2>",
        _markdown_lite_to_html(resumen_ejecutivo),
    ]

    plotlyjs_embebido = False
    for grupo in grupos:
        partes.append(f"<h1>{grupo['titulo']}</h1>")
        for titulo_grafica, fig in grupo["figuras"]:
            partes.append(f"<h3>{titulo_grafica}</h3>")
            include_js = not plotlyjs_embebido
            partes.append(pio.to_html(fig, full_html=False, include_plotlyjs=include_js))
            plotlyjs_embebido = True
        partes.append(_markdown_lite_to_html(grupo["analisis"]))

    partes.append(f"<h1>{TITULO_CONCLUSIONES}</h1>{_markdown_lite_to_html(resumen_ejecutivo)}")
    partes.append("</body></html>")
    return "".join(partes)


TITULO_PORTADA_COMPLETO = "Reporte completo — Clientify Analyzer"
TITULO_INDICE = "Índice"
TITULO_RESUMEN_GLOBAL = "Resumen ejecutivo global y Top 5 prioridades"


def build_full_pdf_report(
    *,
    periodo_label: str,
    resumen_ejecutivo_global: str,
    secciones: list[dict],
    fecha_generacion: date | None = None,
) -> bytes:
    """PDF del "Reporte completo" (las 4 secciones en un solo documento):
    portada, índice, resumen ejecutivo global + Top 5 prioridades, y luego
    cada sección con sus grupos (misma estructura que `build_pdf_report`,
    repetida sección por sección).

    `secciones`: lista de `{"titulo": str, "sin_datos": bool, "nota_sin_
    datos": str | None, "grupos": [{"titulo", "figuras", "analisis"}, ...]}`
    — una sección con `sin_datos=True` se omite con una nota en el PDF (su
    `"grupos"` puede venir vacío), sin romper el resto del documento.

    Lanza `ImageExportError` si el dibujo de alguna figura falla (ver
    `build_pdf_report`)."""
    fecha_generacion = fecha_generacion or date.today()
    estilos = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )

    story: list = []

    # --- Portada ---
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph(TITULO_PORTADA_COMPLETO, estilos["titulo_portada"]))
    story.append(Paragraph(f"Período analizado: {periodo_label}", estilos["subtitulo_portada"]))
    story.append(Paragraph(f"Generado el {fecha_generacion.strftime('%d/%m/%Y')}", estilos["subtitulo_portada"]))
    story.append(PageBreak())

    # --- Índice ---
    story.append(Paragraph(TITULO_INDICE, estilos["h1"]))
    story.append(Paragraph(TITULO_RESUMEN_GLOBAL, estilos["cuerpo"]))
    for seccion in secciones:
        nota = " (sin datos — omitida)" if seccion.get("sin_datos") else ""
        story.append(Paragraph(f"{seccion['titulo']}{nota}", estilos["cuerpo"]))
    story.append(PageBreak())

    # --- Resumen ejecutivo global + Top 5 prioridades ---
    story.append(Paragraph(TITULO_RESUMEN_GLOBAL, estilos["h1"]))
    story.extend(_markdown_lite_to_flowables(resumen_ejecutivo_global, estilos))
    story.append(PageBreak())

    # --- Secciones ---
    for seccion in secciones:
        story.append(Paragraph(seccion["titulo"], estilos["h1"]))
        if seccion.get("sin_datos"):
            story.append(Paragraph(
                seccion.get("nota_sin_datos") or "No hay datos disponibles para esta sección.",
                estilos["cuerpo"],
            ))
            story.append(PageBreak())
            continue

        for grupo in seccion["grupos"]:
            story.append(Paragraph(grupo["titulo"], estilos["h2"]))
            for titulo_grafica, fig in grupo["figuras"]:
                png_bytes = _figure_to_png_bytes(fig)
                img = Image(io.BytesIO(png_bytes), width=_IMAGE_DOC_WIDTH_CM * cm, height=_IMAGE_DOC_HEIGHT_CM * cm)
                story.append(Paragraph(titulo_grafica, estilos["h2"]))
                story.append(img)
                story.append(Spacer(1, 0.3 * cm))
            story.extend(_markdown_lite_to_flowables(grupo["analisis"], estilos))
        story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue()
