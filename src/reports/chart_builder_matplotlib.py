"""Construye las mismas 9 figuras de "Marketing e Inversión" que
`chart_builder.py`, pero en matplotlib en vez de Plotly — SOLO para las
imágenes del PDF (`src/reports/pdf_report.py`).

Por qué matplotlib y no Plotly+kaleido: kaleido (el exportador de imágenes
de Plotly a PNG) depende de un Chromium embebido que puede quedarse
colgado indefinidamente sin lanzar ninguna excepción — confirmado en la
máquina del usuario (Windows, entorno local): `fig.to_image()` nunca
vuelve. El PDF SIEMPRE debe poder generarse, en cualquier entorno (Windows
local, Streamlit Cloud), así que sus imágenes ya no dependen de un
navegador — matplotlib es una dependencia pura de pip (Agg backend, sin
proceso externo, no puede "colgarse" esperando un browser).

Mismas fuentes de datos que `chart_builder.py` (`_df_*`, reexportadas
desde ahí) — así el PDF y la app interactiva nunca muestran cifras
distintas, solo cambia el motor de dibujo. El reporte HTML (descarga
SECUNDARIA/opcional, ver `src/ui/report_generator.py`) sigue usando las
figuras de Plotly de `chart_builder.py` sin cambios.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # backend sin GUI/navegador — seguro en cualquier entorno (hilos de Streamlit, servidores sin display)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from src.reports.chart_builder import (
    CHART_TITLES,
    _df_cierres_vs_gasto,
    _df_costo_por_lead,
    _df_gasto_facturado,
    _df_gasto_real,
    _df_gasto_vs_ingresos_redes,
    _df_gasto_vs_valor_proceso,
    _df_gasto_vs_valor_proceso_roas,
    _df_roas_pauta,
    _df_roas_total,
)

_COLOR_GASTO = "#00B5FF"
_COLOR_ING = "#FF2D55"
_COLOR_ROAS = "#34C759"
_COLOR_FACTURADO = "#F59E0B"
_COLOR_VALOR = "#16A34A"

# Mismo tamaño/relación de aspecto que usaba el PNG de kaleido
# (`IMAGE_WIDTH_PX`/`IMAGE_HEIGHT_PX` en `pdf_report.py`, 1100x620) para que
# el documento del PDF no tenga que cambiar sus medidas en cm.
_FIGSIZE = (11.0, 6.2)
_DPI = 150

_LABEL_FONTSIZE = 10
_AXIS_FONTSIZE = 11
_TITLE_FONTSIZE = 13
_TICK_FONTSIZE = 10


def _bars_figure_mpl(df: pd.DataFrame, bar_specs: list[tuple[str, str, str]], yaxis_title: str) -> Figure | None:
    """Barras anchas (una por mes, agrupadas si hay más de 1 serie) con
    etiqueta de valor legible encima de cada barra — equivalente a
    `chart_builder._bars_figure`, dibujado con matplotlib."""
    if df.empty:
        return None

    categorias = df["Mes_Año"].drop_duplicates().tolist()
    x = np.arange(len(categorias))
    n_series = len(bar_specs)
    ancho_total = 0.82
    ancho_barra = ancho_total / max(n_series, 1)

    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)

    max_y = 0.0
    for i, (value_col, name, color) in enumerate(bar_specs):
        if value_col not in df.columns:
            continue
        valores = df[value_col].tolist()
        max_y = max(max_y, max(valores, default=0.0))
        offset = x - ancho_total / 2 + ancho_barra * i + ancho_barra / 2
        barras = ax.bar(offset, valores, width=ancho_barra, color=color, label=name)
        etiquetas = [f"${v:,.0f}" for v in valores]
        ax.bar_label(barras, labels=etiquetas, padding=3, fontsize=_LABEL_FONTSIZE)

    ax.set_xticks(x)
    ax.set_xticklabels(categorias, rotation=45, ha="right", fontsize=_TICK_FONTSIZE)
    ax.set_ylabel(yaxis_title or "Valor (USD)", fontsize=_AXIS_FONTSIZE)
    ax.set_ylim(0, max_y * 1.25 if max_y > 0 else 1)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    if n_series > 1:
        ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.14), ncol=n_series, frameon=False, fontsize=_AXIS_FONTSIZE)
    fig.tight_layout()
    return fig


def _bars_and_line_figure_mpl(
    df: pd.DataFrame,
    bar_specs: list[tuple[str, str, str]],
    line_spec: tuple[str, str, str, str],
    bar_yaxis_title: str,
    line_yaxis_title: str,
    money_bars: bool = True,
) -> Figure | None:
    """2 PANELES APILADOS (barras arriba, línea de ROAS/tendencia abajo) —
    mismo criterio que `src.ui.charts.build_stacked_bar_line_figure`: la
    línea nunca puede tapar las etiquetas de valor de las barras porque
    viven en ejes Y distintos. Equivalente a
    `chart_builder._bars_and_line_figure`."""
    if df.empty:
        return None

    categorias = df["Mes_Año"].drop_duplicates().tolist()
    x = np.arange(len(categorias))
    n_series = len(bar_specs)
    ancho_total = 0.82
    ancho_barra = ancho_total / max(n_series, 1)

    fig, (ax_bar, ax_line) = plt.subplots(
        2, 1, figsize=_FIGSIZE, dpi=_DPI, sharex=True, height_ratios=(0.70, 0.30),
    )

    max_bar = 0.0
    for i, (value_col, name, color) in enumerate(bar_specs):
        valores = df[value_col].tolist()
        max_bar = max(max_bar, max(valores, default=0.0))
        offset = x - ancho_total / 2 + ancho_barra * i + ancho_barra / 2
        barras = ax_bar.bar(offset, valores, width=ancho_barra, color=color, label=name)
        etiquetas = [f"${v:,.0f}" if money_bars else f"{v:,.0f}" for v in valores]
        ax_bar.bar_label(barras, labels=etiquetas, padding=3, fontsize=_LABEL_FONTSIZE)

    ax_bar.set_ylabel(bar_yaxis_title, fontsize=_AXIS_FONTSIZE)
    ax_bar.set_ylim(0, max_bar * 1.25 if max_bar > 0 else 1)
    if money_bars:
        ax_bar.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax_bar.grid(axis="y", color="#E5E7EB", linewidth=0.8, zorder=0)
    ax_bar.set_axisbelow(True)
    for spine in ("top", "right"):
        ax_bar.spines[spine].set_visible(False)
    if n_series > 1:
        ax_bar.legend(loc="upper left", bbox_to_anchor=(0.0, 1.22), ncol=n_series, frameon=False, fontsize=_AXIS_FONTSIZE)

    line_col, line_name, line_color, line_fmt = line_spec
    valores_linea = df[line_col].tolist()
    max_linea = max(valores_linea, default=0.0)
    ax_line.plot(x, valores_linea, color=line_color, linewidth=2.5, marker="o", markersize=6, label=line_name)
    for xi, v in zip(x, valores_linea):
        if v:
            ax_line.annotate(
                line_fmt.format(v), xy=(xi, v), xytext=(0, 8), textcoords="offset points",
                ha="center", fontsize=_LABEL_FONTSIZE, color=line_color,
            )
    ax_line.set_ylabel(line_yaxis_title, fontsize=_AXIS_FONTSIZE)
    ax_line.set_ylim(0, max_linea * 1.25 if max_linea > 0 else 1)
    ax_line.grid(axis="y", color="#E5E7EB", linewidth=0.8, zorder=0)
    ax_line.set_axisbelow(True)
    for spine in ("top", "right"):
        ax_line.spines[spine].set_visible(False)

    ax_line.set_xticks(x)
    ax_line.set_xticklabels(categorias, rotation=45, ha="right", fontsize=_TICK_FONTSIZE)

    fig.tight_layout()
    return fig


def build_gasto_real_mpl(gasto_raw: pd.DataFrame, anio) -> Figure | None:
    df = _df_gasto_real(gasto_raw, anio)
    return _bars_figure_mpl(df, [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO)], "Gasto en pauta (USD)")


def build_gasto_facturado_mpl(billed_raw: pd.DataFrame | None, anio) -> Figure | None:
    df = _df_gasto_facturado(billed_raw, anio)
    if df.empty:
        return None
    return _bars_figure_mpl(df, [("Importe", "Facturado (USD)", _COLOR_FACTURADO)], "Total facturado (USD)")


def build_gasto_vs_ingresos_redes_mpl(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> Figure | None:
    ancho = _df_gasto_vs_ingresos_redes(gasto_raw, df_clientify, anio)
    if ancho.empty:
        return None
    return _bars_figure_mpl(
        ancho,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Ingreso_Redes", "Ingresos por redes (USD)", "#FF7F0E")],
        "Valor (USD)",
    )


def build_roas_pauta_mpl(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> Figure | None:
    df = _df_roas_pauta(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure_mpl(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Ingreso_CuotaInicial", "Ingreso por cuota inicial (USD)", _COLOR_ING)],
        ("ROAS", "ROAS (Ingreso / Gasto)", _COLOR_ROAS, "{:.2f}x"),
        "Valor (USD)", "ROAS (x)",
    )


def build_costo_por_lead_mpl(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> Figure | None:
    df = _df_costo_por_lead(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure_mpl(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO)],
        ("Valor_por_Lead", "Costo por lead (USD)", "#117A65", "${:.2f}"),
        "Gasto en pauta (USD)", "Costo por lead (USD)",
    )


def build_roas_total_mpl(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> Figure | None:
    df = _df_roas_total(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure_mpl(
        df,
        [("Gasto_Total", "Gasto total (pauta + honorarios) USD", _COLOR_GASTO), ("Ingreso_CuotaInicial", "Ingreso por cuota inicial (USD)", _COLOR_ING)],
        ("ROAS", "ROAS (Ingreso / Gasto)", _COLOR_ROAS, "{:.2f}x"),
        "Valor (USD)", "ROAS (x)",
    )


def build_cierres_vs_gasto_mpl(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> Figure | None:
    df = _df_cierres_vs_gasto(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure_mpl(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO)],
        ("Cierres_Redes", "Cierres con origen en redes", "#117A65", "{:.0f}"),
        "Gasto en pauta (USD)", "Cantidad de cierres (redes)",
        money_bars=True,
    )


def build_gasto_vs_valor_proceso_mpl(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> Figure | None:
    df = _df_gasto_vs_valor_proceso(gasto_raw, df_clientify, anio)
    return _bars_figure_mpl(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Valor_Proceso_Pauta", "Valor Total del Proceso (USD)", _COLOR_VALOR)],
        "Valor (USD)",
    )


def build_gasto_vs_valor_proceso_roas_mpl(gasto_raw: pd.DataFrame, df_clientify: pd.DataFrame, anio) -> Figure | None:
    df = _df_gasto_vs_valor_proceso_roas(gasto_raw, df_clientify, anio)
    return _bars_and_line_figure_mpl(
        df,
        [("Importe", "Gasto en pauta (USD)", _COLOR_GASTO), ("Valor_Proceso_Pauta", "Valor Total del Proceso (USD)", _COLOR_ING)],
        ("ROAS", "ROAS (Valor Proceso / Gasto)", _COLOR_ROAS, "{:.2f}x"),
        "Valor (USD)", "ROAS (x)",
    )


def build_figures_by_group_mpl(
    gasto_raw: pd.DataFrame,
    df_clientify: pd.DataFrame,
    billed_raw: pd.DataFrame | None,
    anio,
) -> dict[str, list[tuple[str, Figure]]]:
    """Equivalente matplotlib de `chart_builder.build_figures_by_group` —
    mismo agrupamiento lógico (ver `src/analytics/report_payload.py`), para
    las imágenes del PDF."""
    por_grupo = {
        "gasto_y_facturado": [
            (CHART_TITLES["gasto_real"], build_gasto_real_mpl(gasto_raw, anio)),
            (CHART_TITLES["gasto_facturado"], build_gasto_facturado_mpl(billed_raw, anio)),
        ],
        "gasto_vs_ingresos_y_roas": [
            (CHART_TITLES["gasto_vs_ingresos_redes"], build_gasto_vs_ingresos_redes_mpl(gasto_raw, df_clientify, anio)),
            (CHART_TITLES["roas_pauta"], build_roas_pauta_mpl(gasto_raw, df_clientify, anio)),
        ],
        "costo_por_lead": [
            (CHART_TITLES["costo_por_lead"], build_costo_por_lead_mpl(gasto_raw, df_clientify, anio)),
        ],
        "roas_total": [
            (CHART_TITLES["roas_total"], build_roas_total_mpl(gasto_raw, df_clientify, anio)),
        ],
        "cierres_y_valor_proceso": [
            (CHART_TITLES["cierres_vs_gasto"], build_cierres_vs_gasto_mpl(gasto_raw, df_clientify, anio)),
            (CHART_TITLES["gasto_vs_valor_proceso"], build_gasto_vs_valor_proceso_mpl(gasto_raw, df_clientify, anio)),
            (CHART_TITLES["gasto_vs_valor_proceso_roas"], build_gasto_vs_valor_proceso_roas_mpl(gasto_raw, df_clientify, anio)),
        ],
    }
    return {
        grupo_id: [(titulo, fig) for titulo, fig in pares if fig is not None]
        for grupo_id, pares in por_grupo.items()
    }
