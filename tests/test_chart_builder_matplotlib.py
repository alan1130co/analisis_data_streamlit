"""Tests de `src/reports/chart_builder_matplotlib.py` — las imágenes del
PDF del reporte de Marketing e Inversión (Problema 2 de la tarea: antes
dependían de Plotly+kaleido, que se cuelga indefinidamente en Windows sin
Chromium; ahora matplotlib, puro Python/C, nunca se cuelga).

Verifica:
- Las 9 figuras se arman con datos reales (sin mockear nada — matplotlib
  con backend "Agg" no necesita pantalla ni navegador, corre en cualquier
  entorno de CI).
- Barras ANCHAS y etiquetas LEGIBLES (Problema 1, mismo criterio que las
  gráficas interactivas): una sola llamada a `ax.bar` por serie (no una
  por mes — el mismo bug que `ad_spend.py` podría reproducirse acá si se
  armara mal), con texto de etiqueta en tamaño legible.
- Barra(s) y línea de ROAS/tendencia viven en 2 PANELES SEPARADOS (2 Axes),
  igual que las gráficas interactivas (`src/ui/charts.py`), para que la
  línea nunca tape las etiquetas de valor de las barras.
- `_figure_to_png_bytes` (vía `pdf_report`) devuelve PNG válido para cada
  figura — sin mocks, exportación real.
"""
import matplotlib

matplotlib.use("Agg")

import pandas as pd

from src.reports.chart_builder_matplotlib import (
    build_figures_by_group_mpl,
    build_gasto_real_mpl,
    build_roas_pauta_mpl,
)
from src.reports.pdf_report import _figure_to_png_bytes


def _gasto_raw(n_meses: int = 9) -> pd.DataFrame:
    return pd.DataFrame([
        {"Fecha": f"01/0{m}/2026" if m < 10 else f"01/{m}/2026", "Divisa": "USD", "Importe": 1000 + m * 300}
        for m in range(1, n_meses + 1)
    ])


def _df_clientify(n_meses: int = 9) -> pd.DataFrame:
    rows = []
    for m in range(1, n_meses + 1):
        mes = f"0{m}" if m < 10 else str(m)
        rows.append({
            "creado": pd.Timestamp(f"2026-{mes}-01"), "estado": "activo",
            "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
            "canal online": "paid social",
            "Fecha de cierre": pd.Timestamp(f"2026-{mes}-05"), "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
            "Cuota inicial pactada": str(300 + m * 10), "Valor total del proceso": str(3000 + m * 100),
        })
    return pd.DataFrame(rows)


class TestBuildGastoRealMpl:
    def test_barras_anchas_una_sola_llamada_por_serie(self):
        """Regresión del bug de Problema 1: UN solo `BarContainer` (no uno
        por mes) con las 9 barras adentro — si se armara "un `ax.bar` por
        mes" (el equivalente matplotlib del bug de `color="Mes_Año"` en
        Plotly), este assert fallaría."""
        fig = build_gasto_real_mpl(_gasto_raw(9), 2026)
        assert fig is not None
        ax = fig.axes[0]
        assert len(ax.containers) == 1
        assert len(ax.containers[0]) == 9

    def test_etiquetas_de_valor_legibles(self):
        fig = build_gasto_real_mpl(_gasto_raw(3), 2026)
        ax = fig.axes[0]
        # `ax.bar_label` agrega los textos como `Text` sueltos del Axes.
        etiquetas = [t for t in ax.texts if t.get_text().startswith("$")]
        assert len(etiquetas) == 3
        for etiqueta in etiquetas:
            assert etiqueta.get_fontsize() >= 9

    def test_sin_datos_devuelve_none(self):
        assert build_gasto_real_mpl(pd.DataFrame(), 2026) is None

    def test_rango_y_deja_margen_para_la_etiqueta_mas_alta(self):
        fig = build_gasto_real_mpl(_gasto_raw(3), 2026)
        ax = fig.axes[0]
        ymin, ymax = ax.get_ylim()
        max_valor = max(1000 + m * 300 for m in range(1, 4))
        assert ymax > max_valor


class TestBuildRoasPautaMpl:
    def test_barras_y_linea_en_paneles_separados(self):
        """2 Axes apilados (barras arriba, línea de ROAS abajo) — nunca el
        mismo panel con eje secundario, mismo criterio que
        `src.ui.charts.build_stacked_bar_line_figure` (bug reportado
        2026-10-07: la línea podía tapar las etiquetas de las barras)."""
        fig = build_roas_pauta_mpl(_gasto_raw(6), _df_clientify(6), 2026)
        assert fig is not None
        assert len(fig.axes) == 2
        ax_bar, ax_line = fig.axes
        assert len(ax_bar.containers) == 2  # Gasto + Ingreso por cuota inicial
        assert len(ax_line.lines) == 1


class TestBuildFiguresByGroupMpl:
    def test_arma_las_9_figuras_agrupadas(self):
        grupos = build_figures_by_group_mpl(_gasto_raw(6), _df_clientify(6), None, 2026)
        total_figuras = sum(len(figs) for figs in grupos.values())
        assert total_figuras == 8  # 9 menos "gasto_facturado" (sin billed_raw)
        assert set(grupos.keys()) == {
            "gasto_y_facturado", "gasto_vs_ingresos_y_roas", "costo_por_lead",
            "roas_total", "cierres_y_valor_proceso",
        }

    def test_cada_figura_exporta_a_png_valido_sin_kaleido(self):
        """Exportación REAL (sin mocks) de las figuras del reporte —
        confirma que matplotlib nunca se cuelga ni depende de un
        navegador."""
        grupos = build_figures_by_group_mpl(_gasto_raw(4), _df_clientify(4), None, 2026)
        for figs in grupos.values():
            for _titulo, fig in figs:
                png_bytes = _figure_to_png_bytes(fig)
                assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
