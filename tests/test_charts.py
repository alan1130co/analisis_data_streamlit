"""Tests de `src/ui/charts.py::build_stacked_bar_line_figure` — el helper
compartido de 2 paneles apilados (barras arriba, línea abajo) que reemplaza
el patrón de "mismo panel + eje Y secundario" en las 6 gráficas de
"Marketing e Inversión" con barra(s) + línea (bug reportado 2026-10-07: la
línea/sus etiquetas tapaban las etiquetas de valor de las barras).
"""
import plotly.graph_objects as go

from src.ui.charts import build_stacked_bar_line_figure


def _build(bar_count: int = 1) -> go.Figure:
    bar_traces = [
        go.Bar(x=["Marzo 2025", "Abril 2025"], y=[100, 200], name=f"Barra {i}", text=["$100", "$200"], textposition="outside")
        for i in range(bar_count)
    ]
    line_trace = go.Scatter(
        x=["Marzo 2025", "Abril 2025"], y=[2.5, 3.1], name="Línea",
        mode="lines+markers+text", text=["2.50x", "3.10x"], textposition="top center",
    )
    return build_stacked_bar_line_figure(
        bar_traces, line_trace,
        categoryarray=["Marzo 2025", "Abril 2025"],
        bar_yaxis=dict(title_text="Valor (USD)", range=[0, 250]),
        line_yaxis=dict(title_text="ROAS", range=[0, 3.875]),
    )


def test_estructura_2_filas_de_subplots():
    """`rows=2, cols=1` real — confirmado por la presencia de `yaxis2`
    (fila 2) con un dominio vertical DISTINTO al de `yaxis` (fila 1), no un
    eje secundario superpuesto en el mismo panel."""
    fig = _build()
    assert fig.layout.yaxis2 is not None
    dom1 = fig.layout.yaxis.domain
    dom2 = fig.layout.yaxis2.domain
    assert dom1 != dom2
    # Fila 1 (barras) arriba, fila 2 (línea) abajo — dominio de y1 por
    # encima del de y2 en coordenadas de figura (0=abajo, 1=arriba).
    assert dom1[0] > dom2[1]


def test_eje_x_compartido():
    """`shared_xaxes=True` real: el eje X de la fila 1 debe estar
    encadenado ("matches") al de la fila 2, no ser independiente — así
    ambos paneles se mueven/hacen zoom juntos."""
    fig = _build()
    assert fig.layout.xaxis.matches == "x2"


def test_sin_yaxis_secundario_superpuesto():
    """Ya NO debe existir un eje Y secundario tipo "overlaying" en el mismo
    panel (el patrón viejo que permitía que la línea tapara las barras) —
    `yaxis2` debe ser un panel propio (sin `overlaying`), no
    `overlaying="y"`."""
    fig = _build()
    assert fig.layout.yaxis2.overlaying is None


def test_barras_en_fila_1_linea_en_fila_2():
    fig = _build(bar_count=2)
    bar_traces = [t for t in fig.data if t.type == "bar"]
    line_traces = [t for t in fig.data if t.type == "scatter"]
    assert len(bar_traces) == 2
    assert len(line_traces) == 1
    for bar in bar_traces:
        assert bar.xaxis in (None, "x")
        assert bar.yaxis in (None, "y")
    assert line_traces[0].xaxis == "x2"
    assert line_traces[0].yaxis == "y2"


def test_headroom_de_cada_panel_se_respeta():
    """El `range` pasado en `bar_yaxis`/`line_yaxis` (ya con headroom
    calculado por el caller, ej. `max * 1.25`) se refleja tal cual en el
    layout de cada panel."""
    fig = _build()
    assert list(fig.layout.yaxis.range) == [0, 250]
    assert list(fig.layout.yaxis2.range) == [0, 3.875]


def test_categoryarray_y_etiquetas_presentes():
    fig = _build()
    assert fig.layout.xaxis2.categoryarray is not None
    assert list(fig.layout.xaxis2.categoryarray) == ["Marzo 2025", "Abril 2025"]
    for trace in fig.data:
        assert trace.text is not None and len(trace.text) == 2


def test_cliponaxis_false_en_todas_las_trazas():
    """Las etiquetas de valor no deben recortarse contra el borde del
    panel — mismo criterio que el resto de "Marketing e Inversión"."""
    fig = _build()
    for trace in fig.data:
        if trace.type == "bar":
            assert trace.cliponaxis is False


def test_xaxis_range_de_zoom_se_aplica_a_ambos_paneles():
    """El rango de "zoom" (mes puntual, ver `ad_spend.compact_month_xaxis_
    range`) debe aplicarse a los 2 paneles (eje X compartido)."""
    bar_traces = [go.Bar(x=["Marzo 2026"], y=[100], text=["$100"], textposition="outside")]
    line_trace = go.Scatter(x=["Marzo 2026"], y=[3.0], text=["3.00x"], textposition="top center")
    fig = build_stacked_bar_line_figure(
        bar_traces, line_trace,
        categoryarray=["Enero 2026", "Marzo 2026"],
        bar_yaxis=dict(title_text="Valor", range=[0, 125]),
        line_yaxis=dict(title_text="ROAS", range=[0, 4]),
        xaxis_range=(0.5, 1.5),
    )
    assert list(fig.layout.xaxis.range) == [0.5, 1.5]
    assert list(fig.layout.xaxis2.range) == [0.5, 1.5]


def test_leyenda_unificada_arriba():
    fig = _build()
    assert fig.layout.legend.orientation == "h"
    assert fig.layout.legend.y > 1.0  # por encima del área de trazado
