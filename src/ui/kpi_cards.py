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


_FILA_1_CANTIDAD = 6  # Gestión Comercial (13 tarjetas): fila 1 = primeras 6, fila 2 = las últimas 7.


def _build_cards_html(kpis, data, prev_data, metrics_prev) -> str:
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
    return "".join(cards)


def render_kpi_cards(
    metrics: Metrics,
    metrics_prev: Metrics | None = None,
    team: str = "Todos",
) -> None:
    """Renderiza la grilla de tarjetas con los KPIs principales, en 2 filas:
    la primera con las primeras `_FILA_1_CANTIDAD` tarjetas de
    `get_kpi_definitions(team)`, la segunda con el resto — mismo orden que
    la lista original, solo se corta en dos `<div class="kpi-grid">`
    independientes (misma clase CSS reutilizada, sigue siendo responsive
    igual que antes de partirla en 2 filas)."""
    data = metrics.to_dict()
    prev_data = metrics_prev.to_dict() if metrics_prev is not None else {}

    kpis = get_kpi_definitions(team)
    fila_1 = kpis[:_FILA_1_CANTIDAD]
    fila_2 = kpis[_FILA_1_CANTIDAD:]

    st.markdown(
        f'<div class="kpi-grid">{_build_cards_html(fila_1, data, prev_data, metrics_prev)}</div>',
        unsafe_allow_html=True,
    )
    if fila_2:
        st.markdown(
            f'<div class="kpi-grid">{_build_cards_html(fila_2, data, prev_data, metrics_prev)}</div>',
            unsafe_allow_html=True,
        )

    with st.expander("Desglose de cierres por etapa"):
        st.caption(
            "Cuenta contratos válidos (estado ≠ \"inactivo\") cuya fecha de "
            "cierre correspondiente cae en el mes seleccionado, en cualquier canal."
        )
        etapas = [
            ("1er cierre", metrics.cierres_1),
            ("2do cierre", metrics.cierres_2),
            ("3er cierre", metrics.cierres_3),
            ("4to cierre", metrics.cierres_4),
        ]
        # HTML/CSS custom (no st.columns): st.columns apila verticalmente en
        # mobile por defecto, y acá queremos 2x2 en pantallas chicas, no 4
        # filas — ver .etapa-grid en kpi_cards.css / responsive.css.
        etapa_cards = "".join(
            f'<div class="etapa-card">'
            f'<div class="etapa-value">{format_int(valor)}</div>'
            f'<div class="etapa-label">{label}</div>'
            f'</div>'
            for label, valor in etapas
        )
        st.markdown(
            f'<div class="etapa-grid">{etapa_cards}</div>',
            unsafe_allow_html=True,
        )
