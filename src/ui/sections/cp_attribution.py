from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.cp_attribution import match_cp_with_closures, summary_by_video


def render_cp_attribution(
    df_cp: pd.DataFrame | None,
    df_clientify: pd.DataFrame,
    year: int,
    month: int,
) -> None:
    """Sección de atribución REAL de cierres desde archivos CP de Meta."""

    st.markdown("### 🎯 Atribución REAL de cierres por CP de Meta")

    if df_cp is None or df_cp.empty:
        st.info(
            "Subí uno o varios archivos CSV de Clientes Potenciales (CP) de Meta "
            "desde el sidebar. El sistema los cruza contra Clientify por teléfono y email "
            "para saber EXACTAMENTE qué cliente cerró desde qué video."
        )
        return

    # Cruzar
    df_matches = match_cp_with_closures(df_cp, df_clientify, year, month)
    summary = summary_by_video(df_cp, df_matches)

    if summary.empty:
        st.info(f"No hay CP para {year}-{month:02d}.")
        return

    # === KPIs EJECUTIVOS ARRIBA ===
    total_videos = len(summary)
    total_cp = int(summary["CP generados"].sum())
    total_cierres = int(summary["Cerraron"].sum())
    tasa_general = round(total_cierres / total_cp * 100, 1) if total_cp else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🎥 Videos activos", total_videos)
    with c2:
        st.metric("👥 CP generados", f"{total_cp:,}")
    with c3:
        st.metric("🎯 Cierres identificados", total_cierres)
    with c4:
        st.metric("📊 Tasa conversión", f"{tasa_general}%")

    st.markdown("")

    # === BAR CHART: RANKING DE VIDEOS POR CIERRES ===
    if total_cierres > 0:
        st.markdown("#### 🏆 Ranking de videos por cierres reales")
        summary_chart = summary.head(10).copy()
        # Truncar nombres largos para el eje
        summary_chart["Video_corto"] = summary_chart["Video"].apply(
            lambda x: x[:45] + "..." if len(str(x)) > 45 else x
        )
        fig = px.bar(
            summary_chart,
            x="Cerraron",
            y="Video_corto",
            orientation="h",
            text="Cerraron",
            color="Cerraron",
            color_continuous_scale="Blues",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            height=max(280, 45 * len(summary_chart)),
            margin=dict(l=20, r=60, t=20, b=20),
            yaxis=dict(autorange="reversed"),
            showlegend=False,
            xaxis_title="Cierres reales",
            yaxis_title="",
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # === TABLA RESUMEN POR VIDEO ===
    st.markdown("#### 📋 Resumen por video")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    # === DETALLE EXPANDIBLE ===
    if not df_matches.empty:
        with st.expander(f"👥 Ver los {len(df_matches)} clientes cerrados y de qué video vinieron"):
            detail_display = df_matches[[
                "Nombre CP (Meta)", "Nombre Clientify", "Teléfono",
                "Video", "Conjunto", "Fecha cierre", "Matcheo"
            ]].copy()
            st.dataframe(detail_display, use_container_width=True, hide_index=True)
    else:
        st.warning(
            "No se encontraron matches entre los CP y los cierres de Clientify en el período. "
            "Verificá que los teléfonos y emails coincidan entre ambos sistemas."
        )

    st.caption(
        f"Atribución 100% REAL basada en cruce de teléfono/email entre Meta CP y Clientify. "
        f"Los cierres que no matchean pueden ser referidos, orgánicos o clientes que no dejaron "
        f"los mismos datos en ambos sistemas."
    )
