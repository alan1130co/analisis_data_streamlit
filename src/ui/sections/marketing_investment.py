from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.marketing_investment import (
    compute_investment_metrics,
    top_anuncios_del_mes,
)


def render_marketing_investment(
    df_clientify: pd.DataFrame,
    df_meta: pd.DataFrame | None,
    year: int,
    month: int,
) -> None:
    """Sección 'Inversión en pauta'. Si no hay CSV de Meta, muestra info."""

    st.markdown("### 💰 Inversión en pauta")

    if df_meta is None or df_meta.empty:
        st.info(
            "Cargá un CSV de Meta Ads Manager desde el sidebar para ver las métricas "
            "de inversión y costos por lead/cierre."
        )
        return

    metrics = compute_investment_metrics(df_clientify, df_meta, year, month)

    if metrics.gasto_total == 0:
        st.info("No hay gasto registrado en Meta para el mes seleccionado.")
        return

    # === KPI cards principales — 4 columnas ===
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💵 Gasto en pauta (USD)", f"${metrics.gasto_total:,.2f}")
    with c2:
        st.metric("👤 Costo por lead", f"${metrics.costo_por_lead:,.2f}")
    with c3:
        st.metric("🎯 Costo por cierre (CAC)", f"${metrics.costo_por_cierre:,.2f}")
    with c4:
        st.metric("📊 CPM promedio", f"${metrics.cpm_promedio:,.2f}")

    # === Métricas de Meta — segunda fila ===
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.metric("👁 Impresiones", f"{metrics.impresiones:,}")
    with c6:
        st.metric("🔍 Alcance", f"{metrics.alcance:,}")
    with c7:
        st.metric("🖱 Clics en enlace", f"{metrics.clics:,}")
    with c8:
        st.metric("💬 Contactos Meta", f"{metrics.nuevos_contactos}")

    st.markdown("")

    # === Embudo ===
    st.markdown("#### 📊 Embudo de la pauta")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
            <div style="padding:12px;border-radius:8px;background:#F8FAFC">
                <p style="margin:0;font-size:13px;color:#64748B">Conversión de la pauta</p>
                <p style="margin:4px 0;font-size:20px;font-weight:600">
                    {metrics.clics:,} clics → {metrics.nuevos_contactos} contactos →
                    {metrics.leads_pauta} leads → {metrics.cierres_pauta} cierres
                </p>
                <p style="margin:0;font-size:13px;color:#64748B">
                    Tasa clic→contacto: <b>{metrics.tasa_conversion_clic}%</b>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        fig = go.Figure(data=[go.Bar(
            x=["Clics", "Contactos Meta", "Leads Clientify", "Cierres"],
            y=[metrics.clics, metrics.nuevos_contactos, metrics.leads_pauta, metrics.cierres_pauta],
            marker=dict(color=["#94A3B8", "#0EA5E9", "#2563EB", "#16A34A"]),
            text=[metrics.clics, metrics.nuevos_contactos, metrics.leads_pauta, metrics.cierres_pauta],
            textposition="outside",
        )])
        fig.update_layout(
            height=240, margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False, yaxis=dict(showgrid=True),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("")

    # === Top anuncios ===
    st.markdown("#### 🏆 Top 5 anuncios por inversión")
    top = top_anuncios_del_mes(df_meta, year, month, top_n=5)
    if top.empty:
        st.info("No hay anuncios para mostrar.")
    else:
        top_display = top.copy()
        top_display["Gasto USD"] = top_display["Gasto USD"].apply(lambda x: f"${x:,.2f}")
        top_display["Costo/Contacto"] = top_display["Costo/Contacto"].apply(
            lambda x: f"${x:,.2f}" if x else "—"
        )
        top_display["Impresiones"] = top_display["Impresiones"].apply(lambda x: f"{int(x):,}")
        top_display["Clics"] = top_display["Clics"].apply(lambda x: f"{int(x):,}")
        st.dataframe(top_display, use_container_width=True, hide_index=True)

    st.caption(
        f"Datos de Meta Ads Manager + Clientify para {year}-{month:02d}. "
        f"Cuando tengas el dato de ingreso por cierre, podemos activar ROI y ROAS."
    )
