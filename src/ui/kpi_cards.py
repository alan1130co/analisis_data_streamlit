"""Tarjetas de KPIs estilo Power BI (la fila de cards de la imagen)."""
import streamlit as st

from src.analytics.metrics import Metrics
from src.analytics.kpis import get_kpi_definitions
from src.utils.formatters import format_int, format_percent, format_percent_raw


def _format_value(value, fmt: str) -> str:
    if fmt == "percent":
        return format_percent(value)
    if fmt == "percent_raw":
        return format_percent_raw(value)
    return format_int(value)


def _delta_html(current, prev, fmt: str) -> str:
    delta = current - prev
    if fmt == "percent":
        pts = delta * 100
        if abs(pts) < 0.05:
            return '<div class="kpi-delta kpi-delta-flat">0.0 pts</div>'
        sign = "+" if pts > 0 else ""
        css = "kpi-delta-up" if pts > 0 else "kpi-delta-down"
        return f'<div class="kpi-delta {css}">{sign}{pts:.1f} pts</div>'
    elif fmt == "percent_raw":
        pts = delta
        if abs(pts) < 0.05:
            return '<div class="kpi-delta kpi-delta-flat">0.0 pts</div>'
        sign = "+" if pts > 0 else ""
        css = "kpi-delta-up" if pts > 0 else "kpi-delta-down"
        return f'<div class="kpi-delta {css}">{sign}{pts:.1f} pts</div>'
    else:
        d = int(delta)
        if d == 0:
            return '<div class="kpi-delta kpi-delta-flat">0</div>'
        css = "kpi-delta-up" if d > 0 else "kpi-delta-down"
        formatted = f"{abs(d):,}".replace(",", ".")
        sign = "+" if d > 0 else "-"
        return f'<div class="kpi-delta {css}">{sign}{formatted}</div>'


def render_kpi_cards(
    metrics: Metrics,
    metrics_prev: Metrics | None = None,
    team: str = "Todos",
) -> None:
    """Renderiza la grilla de tarjetas con los KPIs principales."""
    data = metrics.to_dict()
    prev_data = metrics_prev.to_dict() if metrics_prev is not None else {}

    kpis = get_kpi_definitions(team)

    cards = []
    for kpi in kpis:
        value = data.get(kpi.key, 0)
        formatted = _format_value(value, kpi.format)

        delta = ""
        if metrics_prev is not None:
            prev_val = prev_data.get(kpi.key, 0)
            delta = _delta_html(value, prev_val, kpi.format)

        cards.append(
            f'<div class="kpi-card">'
            f'<div class="kpi-value" style="color: {kpi.color};">{formatted}</div>'
            f'<div class="kpi-label">{kpi.icon} {kpi.label}</div>'
            f'{delta}'
            f'</div>'
        )

    st.markdown(
        f'<div class="kpi-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Desglose de cierres por etapa"):
        st.caption(
            "Cuenta contratos válidos (estado ≠ \"inactivo\") cuya fecha de "
            "cierre correspondiente cae en el mes seleccionado, en cualquier canal."
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("1er cierre", metrics.cierres_1)
        c2.metric("2do cierre", metrics.cierres_2)
        c3.metric("3er cierre", metrics.cierres_3)
        c4.metric("4to cierre", metrics.cierres_4)
