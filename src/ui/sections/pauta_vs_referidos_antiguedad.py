"""Sección: Pauta vs Referidos según antigüedad del lead (mismo mes vs. antes)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.breakdowns import (
    available_periods,
    cierres_whatsapp_facebook_cp_por_mes_origen,
    pauta_vs_referidos_por_antiguedad_detalle,
)
from src.ui.period_selector import render_period_selector

_TRANSPARENT = "rgba(0,0,0,0)"

_CANAL_ORDER = ["Clientify - Whatsapp", "Formulario de Facebook - Cliente Potencial"]
_CANAL_COLORS = {
    "Clientify - Whatsapp": "#16A34A",
    "Formulario de Facebook - Cliente Potencial": "#7C3AED",
}

_MESES_ABREV = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


def _format_mes_origen(mes_origen: str) -> str:
    """"2026-08" -> "Ago 2026" — etiqueta legible para las porciones de la torta."""
    year_str, month_str = mes_origen.split("-")
    return f"{_MESES_ABREV[int(month_str)]} {year_str}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _shades(base_hex: str, n: int) -> list[str]:
    """Genera `n` tonos derivados de `base_hex` (mismo matiz, luminosidad
    creciente) para diferenciar las porciones de una torta de UN SOLO canal
    — un pie chart necesita un color por porción, no un color plano. El
    primer tono es el color base exacto (el ya usado en la gráfica de
    barras anterior); los siguientes se aclaran progresivamente mezclando
    con blanco."""
    if n <= 1:
        return [base_hex]
    r, g, b = _hex_to_rgb(base_hex)
    shades = []
    for i in range(n):
        t = (i / (n - 1)) * 0.65
        shade = tuple(int(c + (255 - c) * t) for c in (r, g, b))
        shades.append(_rgb_to_hex(shade))
    return shades


def render_pauta_vs_referidos_antiguedad(df_full: pd.DataFrame, year: int, month: int) -> None:
    """Reutiliza el `(year, month)` ya resuelto por el selector propio de la
    sección "📡 Pauta vs Referidos" (`render_pauta_vs_referidos`, que ahora
    lo devuelve) para la tabla de detalle de cierres — esa parte NO tiene
    selector propio.

    La gráfica de "cierres por mes de origen" (2026-09-04), al final de esta
    función, SÍ tiene su propio `st.selectbox` de período, independiente del
    resto — ver comentario junto a `render_period_selector` más abajo.

    2026-09-08: se eliminó la gráfica de barras apiladas por antigüedad
    (cohortes "Llegaron y cerraron este mes" / "Llegaron antes y cerraron
    este mes") y sus 2 métricas — quedaba redundante con la dona "Pauta vs
    Referidos" (`pauta_vs_referidos.py`, sección aparte, sin cambios) y el
    usuario pidió simplificar. `pauta_vs_referidos_por_antiguedad` (la
    función de analytics que la alimentaba) NO se borró — sigue cubierta
    por tests dedicados en `tests/test_breakdowns.py`."""
    st.subheader("🕓 Pauta vs Referidos según antigüedad del lead")

    st.markdown("#### Detalle de cierres")
    detalle = pauta_vs_referidos_por_antiguedad_detalle(df_full, df_full, year, month)
    if detalle.empty:
        st.info("No hay cierres para mostrar en el detalle de este período.")
    else:
        display = detalle.copy()
        display["Fecha de creación"] = display["Fecha de creación"].dt.strftime("%d/%m/%Y")
        display["Fecha de cierre"] = display["Fecha de cierre"].dt.strftime("%d/%m/%Y")
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("#### Cierres de Clientify-Whatsapp y Formulario Facebook-CP por mes de origen")
    # Selector de período INDEPENDIENTE del resto de la sección (tabla de
    # detalle arriba sigue usando el `year`/`month` que recibe la función).
    # Usa `available_periods` (basado en fecha de CIERRE), no
    # `available_months` (basado en "creado") — `cierres_whatsapp_facebook_cp_
    # por_mes_origen` filtra por mes de CIERRE (mismo criterio que
    # `pauta_vs_referidos`, que alimenta la dona en `pauta_vs_referidos.py`
    # con el mismo helper), así que el selector debe ofrecer los mismos
    # meses en los que existen cierres, no meses en los que se crearon leads.
    periods_wf = available_periods(df_full)
    default_year_wf, default_month_wf = periods_wf[0] if periods_wf else (0, 0)
    sel_wf = render_period_selector(
        periods_wf, default_year_wf, default_month_wf,
        key="cierres_wf_mes_origen_periodo",
        label="Período de cierre",
    )
    if sel_wf is None:
        st.info("No hay cierres registrados para esta gráfica.")
        return
    year_wf, month_wf = sel_wf

    # Reutiliza la misma función de analytics (ya trae ambos canales en
    # formato largo, sin cambios) — 2026-09-08b: cada canal se muestra como
    # torta (una porción por mes de origen), en vez de barras.
    data_wf = cierres_whatsapp_facebook_cp_por_mes_origen(df_full, df_full, year_wf, month_wf)
    if data_wf.empty:
        st.info("No hay cierres de estos 2 canales en este período.")
        return

    for canal in _CANAL_ORDER:
        data_canal = data_wf[data_wf["Canal"] == canal].set_index("Mes de Origen")["Cantidad"]
        if data_canal.empty:
            continue
        # Meses propios de ESTE canal únicamente.
        meses_canal = sorted(data_canal.index)
        vals = [int(data_canal.get(m, 0)) for m in meses_canal]
        labels = [_format_mes_origen(m) for m in meses_canal]
        text_labels = [f"{label}: {val}" for label, val in zip(labels, vals)]

        st.markdown(f"##### Cierres de {canal} por mes de origen")
        fig_canal = go.Figure()
        fig_canal.add_trace(go.Pie(
            labels=labels,
            values=vals,
            text=text_labels,
            textinfo="text",
            hovertemplate="%{label}: %{value} cierres (%{percent})<extra></extra>",
            marker=dict(colors=_shades(_CANAL_COLORS[canal], len(labels))),
        ))
        fig_canal.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=30, b=40),
            plot_bgcolor=_TRANSPARENT,
            paper_bgcolor=_TRANSPARENT,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_canal, use_container_width=True)

        total_canal = int(data_canal.sum())
        mes_lider = data_canal.idxmax()
        cantidad_lider = int(data_canal.max())
        cc1, cc2 = st.columns(2)
        cc1.metric(f"Total de cierres — {canal}", f"{total_canal:,}".replace(",", "."))
        cc2.metric("Mes de origen con más cierres", f"{mes_lider} ({cantidad_lider})")
