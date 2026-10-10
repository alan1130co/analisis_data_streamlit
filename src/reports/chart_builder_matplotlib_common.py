"""Helpers matplotlib compartidos por los `chart_builder_matplotlib_*.py`
de las secciones NUEVAS (Segmentación, Embudo, Gestión Comercial) — mismo
criterio visual que `src/reports/chart_builder_matplotlib.py` (Marketing,
no se tocó): barras anchas, etiquetas legibles (>=10pt), sin recortes,
nunca Plotly+kaleido (ver ese módulo para el porqué del backend Agg).

Reemplazos deliberados por limitación de matplotlib (avisado al usuario):
- Dona/pie -> barras horizontales ordenadas desc. (mismo dato, sin depender
  de una forma circular).
- Treemap (cierres por ciudad) -> barras horizontales top-N por volumen.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

_FIGSIZE = (11.0, 6.2)
_DPI = 150
_LABEL_FONTSIZE = 10
_AXIS_FONTSIZE = 11
_TICK_FONTSIZE = 10
_COLOR_DEFAULT = "#00B5FF"


def horizontal_bar_figure(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    *,
    title_x: str = "Cantidad",
    color: str = _COLOR_DEFAULT,
    top_n: int = 15,
) -> Figure | None:
    """Barras horizontales ordenadas desc. por `value_col` — reemplazo fiel
    de dona/treemap para distribuciones por categoría."""
    if df is None or df.empty or label_col not in df.columns or value_col not in df.columns:
        return None
    datos = df.sort_values(value_col, ascending=False).head(top_n)
    categorias = datos[label_col].astype(str).tolist()[::-1]
    valores = datos[value_col].tolist()[::-1]
    if not valores:
        return None

    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)
    y = np.arange(len(categorias))
    barras = ax.barh(y, valores, color=color)
    ax.bar_label(barras, labels=[f"{v:,.0f}" for v in valores], padding=4, fontsize=_LABEL_FONTSIZE)
    ax.set_yticks(y)
    ax.set_yticklabels(categorias, fontsize=_TICK_FONTSIZE)
    ax.set_xlabel(title_x, fontsize=_AXIS_FONTSIZE)
    max_x = max(valores, default=0)
    ax.set_xlim(0, max_x * 1.2 if max_x > 0 else 1)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return fig


def grouped_bar_over_categories_figure(
    df: pd.DataFrame,
    label_col: str,
    value_specs: list[tuple[str, str, str]],
    *,
    title_y: str = "Cantidad",
) -> Figure | None:
    """Barras verticales agrupadas por categoría (varias series sobre el
    mismo eje de categorías — p.ej. Asignados/Calificados/Cierres por asesor,
    o Mes anterior/Mes actual por KPI)."""
    if df is None or df.empty or label_col not in df.columns:
        return None
    categorias = df[label_col].astype(str).tolist()
    x = np.arange(len(categorias))
    n_series = len(value_specs)
    if n_series == 0:
        return None
    ancho_total = 0.82
    ancho_barra = ancho_total / n_series

    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)
    max_y = 0.0
    for i, (value_col, name, color) in enumerate(value_specs):
        if value_col not in df.columns:
            continue
        valores = df[value_col].tolist()
        max_y = max(max_y, max(valores, default=0.0))
        offset = x - ancho_total / 2 + ancho_barra * i + ancho_barra / 2
        barras = ax.bar(offset, valores, width=ancho_barra, color=color, label=name)
        ax.bar_label(barras, labels=[f"{v:,.0f}" for v in valores], padding=3, fontsize=_LABEL_FONTSIZE)

    ax.set_xticks(x)
    ax.set_xticklabels(categorias, rotation=45, ha="right", fontsize=_TICK_FONTSIZE)
    ax.set_ylabel(title_y, fontsize=_AXIS_FONTSIZE)
    ax.set_ylim(0, max_y * 1.25 if max_y > 0 else 1)
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    if n_series > 1:
        ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.14), ncol=n_series, frameon=False, fontsize=_AXIS_FONTSIZE)
    fig.tight_layout()
    return fig


def multi_line_over_time_figure(
    df: pd.DataFrame,
    x_col: str,
    line_specs: list[tuple[str, str, str]],
    *,
    title_y: str = "Cantidad",
) -> Figure | None:
    """Varias líneas sobre el mismo eje de tiempo (tendencia mensual,
    evolución de cierres por canal, etc.)."""
    if df is None or df.empty or x_col not in df.columns:
        return None
    categorias = df[x_col].astype(str).tolist()
    x = np.arange(len(categorias))
    specs_validos = [s for s in line_specs if s[0] in df.columns]
    if not specs_validos:
        return None

    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)
    max_y = 0.0
    for value_col, name, color in specs_validos:
        valores = df[value_col].tolist()
        max_y = max(max_y, max(valores, default=0.0))
        ax.plot(x, valores, color=color, linewidth=2.5, marker="o", markersize=5, label=name)

    ax.set_xticks(x)
    ax.set_xticklabels(categorias, rotation=45, ha="right", fontsize=_TICK_FONTSIZE)
    ax.set_ylabel(title_y, fontsize=_AXIS_FONTSIZE)
    ax.set_ylim(0, max_y * 1.25 if max_y > 0 else 1)
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.14), ncol=len(specs_validos), frameon=False, fontsize=_AXIS_FONTSIZE)
    fig.tight_layout()
    return fig
