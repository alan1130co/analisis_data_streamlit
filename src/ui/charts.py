"""
Gráficos con Plotly para el dashboard.

TODO: implementar gráficos de:
- Evolución mensual de creados / cierres
- Embudo: Creados → Asignados → Calificados → Cierres
- Distribución de cierres por canal
- Ranking de comerciales
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def build_stacked_bar_line_figure(
    bar_traces: list[go.Bar],
    line_trace: go.Scatter,
    *,
    categoryarray: list[str],
    bar_yaxis: dict,
    line_yaxis: dict,
    xaxis_title: str = "Mes y Año",
    xaxis_range: tuple[float, float] | None = None,
    barmode: str = "group",
    bargap: float = 0.25,
    bargroupgap: float = 0.15,
    row_heights: tuple[float, float] = (0.70, 0.30),
    vertical_spacing: float = 0.08,
) -> go.Figure:
    """Figura de 2 PANELES APILADOS (barras arriba, línea abajo, eje X
    compartido) — barras y línea nunca comparten pixeles de altura, así que
    la línea/sus etiquetas no pueden tapar las etiquetas de valor de las
    barras (bug reportado 2026-10-07: con las 2 series en el mismo panel y
    un eje Y secundario, la línea de ROAS/otra métrica podía cruzar
    cualquier altura de las barras sin importar cuánto headroom tuvieran —
    el "collision flip" de `ad_spend.avoid_label_collision_positions` era
    un parche sobre ese problema de fondo, no una solución real).

    Compartido por las 6 gráficas de "Marketing e Inversión" que combinan
    barras + línea (`ad_spend_roas.py`, `ad_spend_total_roas.py`,
    `ad_spend_vs_process_value_roas.py`, `ad_spend_vs_closures.py`,
    `ad_spend_cost_per_lead.py`) para no duplicar la construcción del
    layout en cada una — cada caller sigue armando sus propios `go.Bar`/
    `go.Scatter` (colores, textos, nombres) y solo le pasa los traces ya
    construidos a este helper.

    `bar_traces`: 1 o 2 `go.Bar` (grouped si son 2, ver `barmode`).
    `line_trace`: un único `go.Scatter` (la línea, con su propio
    `textposition` — ya no necesita alternar "top"/"bottom center" para
    evitar a las barras, al vivir en su panel propio; alguna colisión
    etiqueta-contra-etiqueta DENTRO de la línea misma, si llegara a pasar
    con valores muy parecidos entre meses consecutivos, queda fuera de
    alcance de este fix, igual que antes).
    `bar_yaxis`/`line_yaxis`: dict con las claves de `go.layout.YAxis` que
    cada caller ya armaba (`title`, `range`, `tickprefix`, `tickformat`,
    etc.) — SIN `side`/`overlaying` (ya no aplican, cada panel tiene su
    propio eje izquierdo único). `range` en ambos debe incluir headroom
    (`max * 1.25` o similar) para que ninguna etiqueta se recorte contra el
    borde de su panel.
    `categoryarray`: la lista COMPLETA de categorías del eje X (la más
    amplia entre barras/línea, ej. el año completo aunque las barras
    muestren solo un mes puntual) — mismo criterio que usaban las 6
    gráficas antes de este fix.
    `xaxis_range`: rango de "zoom" opcional (ver `ad_spend.compact_month_
    xaxis_range`) cuando Año y Mes son ambos específicos — se aplica a los
    2 paneles (eje X compartido).
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=list(row_heights), vertical_spacing=vertical_spacing,
    )

    for bar in bar_traces:
        fig.add_trace(bar, row=1, col=1)
    fig.add_trace(line_trace, row=2, col=1)

    xaxis_kwargs = dict(type="category", categoryorder="array", categoryarray=categoryarray)
    if xaxis_range is not None:
        xaxis_kwargs["range"] = xaxis_range
    fig.update_xaxes(**xaxis_kwargs, row=1, col=1)
    fig.update_xaxes(**xaxis_kwargs, title_text=xaxis_title, tickangle=-45, row=2, col=1)

    fig.update_yaxes(**bar_yaxis, row=1, col=1)
    fig.update_yaxes(**line_yaxis, row=2, col=1)

    fig.update_layout(
        template="plotly_white",
        barmode=barmode,
        bargap=bargap,
        bargroupgap=bargroupgap,
        legend=dict(x=0.02, y=1.12, orientation="h"),
        margin=dict(t=80, b=20),
    )
    fig.update_traces(cliponaxis=False)
    return fig


def render_funnel(metrics_dict: dict) -> None:
    """Renderiza el embudo de conversión."""
    data = pd.DataFrame({
        "Etapa": ["Creados", "Asignados", "Calificados", "Cierres"],
        "Cantidad": [
            metrics_dict["creados"],
            metrics_dict["asignados"],
            metrics_dict["calificados"],
            metrics_dict["total_cierres"],
        ],
    })
    fig = px.funnel(data, x="Cantidad", y="Etapa", color_discrete_sequence=["#2563EB"])
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300)
    st.plotly_chart(fig, use_container_width=True)
