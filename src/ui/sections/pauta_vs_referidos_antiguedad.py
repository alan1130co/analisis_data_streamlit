"""Sección: Pauta vs Referidos según antigüedad del lead (mismo mes vs. antes)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.breakdowns import (
    COHORTE_MES_ANTERIOR,
    COHORTE_MISMO_MES,
    available_periods,
    cierres_whatsapp_facebook_cp_por_mes_origen,
    pauta_vs_referidos_por_antiguedad,
    pauta_vs_referidos_por_antiguedad_detalle,
)
from src.ui.period_selector import render_period_selector

_TRANSPARENT = "rgba(0,0,0,0)"
_PRIMARY = "#2563EB"
_SUCCESS = "#16A34A"

_COHORTES = [COHORTE_MISMO_MES, COHORTE_MES_ANTERIOR]

_CANAL_ORDER = ["Clientify - Whatsapp", "Formulario de Facebook - Cliente Potencial"]
_CANAL_COLORS = {
    "Clientify - Whatsapp": "#16A34A",
    "Formulario de Facebook - Cliente Potencial": "#7C3AED",
}


def render_pauta_vs_referidos_antiguedad(df_full: pd.DataFrame, year: int, month: int) -> None:
    """Reutiliza el `(year, month)` ya resuelto por el selector propio de la
    sección "📡 Pauta vs Referidos" (`render_pauta_vs_referidos`, que ahora
    lo devuelve) para la dona, las barras apiladas por antigüedad y la tabla
    de detalle — esas 3 partes NO tienen selector propio.

    La gráfica de "cierres por mes de origen" (2026-09-04), al final de esta
    función, SÍ tiene su propio `st.selectbox` de período, independiente del
    resto — ver comentario junto a `render_period_selector` más abajo."""
    st.subheader("🕓 Pauta vs Referidos según antigüedad del lead")

    data = pauta_vs_referidos_por_antiguedad(df_full, df_full, year, month)
    pauta_by_cohorte = data[data["Origen"] == "Pauta"].set_index("Cohorte")["Cantidad"]
    ref_by_cohorte = data[data["Origen"] == "Referidos"].set_index("Cohorte")["Cantidad"]

    pauta_vals = [int(pauta_by_cohorte.get(c, 0)) for c in _COHORTES]
    ref_vals = [int(ref_by_cohorte.get(c, 0)) for c in _COHORTES]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Pauta",
        x=_COHORTES,
        y=pauta_vals,
        marker_color=_PRIMARY,
        text=pauta_vals,
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        name="Referidos",
        x=_COHORTES,
        y=ref_vals,
        marker_color=_SUCCESS,
        text=ref_vals,
        textposition="inside",
    ))
    fig.update_layout(
        barmode="stack",
        height=420,
        margin=dict(l=20, r=20, t=40, b=40),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    total_mismo_mes = int(pauta_by_cohorte.get(COHORTE_MISMO_MES, 0)) + int(ref_by_cohorte.get(COHORTE_MISMO_MES, 0))
    total_mes_anterior = int(pauta_by_cohorte.get(COHORTE_MES_ANTERIOR, 0)) + int(ref_by_cohorte.get(COHORTE_MES_ANTERIOR, 0))

    c1, c2 = st.columns(2)
    c1.metric(COHORTE_MISMO_MES, f"{total_mismo_mes:,}".replace(",", "."))
    c2.metric(COHORTE_MES_ANTERIOR, f"{total_mes_anterior:,}".replace(",", "."))

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
    # Selector de período INDEPENDIENTE del resto de la sección (dona,
    # barras apiladas por antigüedad y tabla de detalle arriba siguen usando
    # el `year`/`month` que recibe la función). Usa `available_periods`
    # (basado en fecha de CIERRE), no `available_months` (basado en
    # "creado") — `cierres_whatsapp_facebook_cp_por_mes_origen` filtra por
    # mes de CIERRE (mismo criterio que `pauta_vs_referidos`, que alimenta
    # la dona de arriba con el mismo helper), así que el selector debe
    # ofrecer los mismos meses en los que existen cierres, no meses en los
    # que se crearon leads.
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

    data_wf = cierres_whatsapp_facebook_cp_por_mes_origen(df_full, df_full, year_wf, month_wf)
    if data_wf.empty:
        st.info("No hay cierres de estos 2 canales en este período.")
        return

    meses = sorted(data_wf["Mes de Origen"].unique())
    pivot = (
        data_wf.pivot(index="Mes de Origen", columns="Canal", values="Cantidad")
        .reindex(meses)
        .fillna(0)
    )

    fig2 = go.Figure()
    for canal in _CANAL_ORDER:
        vals = pivot[canal].tolist() if canal in pivot.columns else [0] * len(meses)
        fig2.add_trace(go.Bar(
            name=canal,
            x=meses,
            y=vals,
            marker_color=_CANAL_COLORS[canal],
            text=[int(v) for v in vals],
            textposition="inside",
        ))
    fig2.update_layout(
        barmode="stack",
        height=420,
        xaxis_title="Mes de Origen",
        margin=dict(l=20, r=20, t=40, b=40),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig2, use_container_width=True)

    por_mes = data_wf.groupby("Mes de Origen")["Cantidad"].sum()
    total_wf = int(por_mes.sum())
    mes_lider = por_mes.idxmax()
    cantidad_lider = int(por_mes.max())

    c3, c4 = st.columns(2)
    c3.metric("Total de cierres (estos 2 canales)", f"{total_wf:,}".replace(",", "."))
    c4.metric("Mes de origen con más cierres", f"{mes_lider} ({cantidad_lider})")
