from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.investment_by_set import investment_by_set


def render_investment_by_set(
    df_meta_sets: pd.DataFrame | None,
    df_clientify: pd.DataFrame,
    year: int,
    month: int,
) -> None:
    st.markdown("### 📊 Inversión por conjunto de anuncios")

    if df_meta_sets is None or df_meta_sets.empty:
        st.info(
            "Cargá un CSV de Conjuntos de Meta Ads desde el sidebar para ver "
            "cuánto invertiste y cuántos contactos generó cada conjunto."
        )
        return

    df = investment_by_set(df_meta_sets, df_clientify, year, month)

    if df.empty:
        st.info(f"No hay datos de Meta para {year}-{month:02d}.")
        return

    # KPIs arriba
    total_gasto = df["Gasto USD"].sum()
    cols_top = st.columns(4)
    cols_top[0].metric("💵 Gasto total", f"${total_gasto:,.2f}")
    if "Contactos" in df.columns:
        total_contactos = int(df["Contactos"].sum())
        cols_top[1].metric("💬 Contactos totales", f"{total_contactos:,}")
        if total_contactos > 0:
            cols_top[2].metric(
                "💸 Costo/contacto promedio",
                f"${total_gasto/total_contactos:,.2f}",
            )
    if "Cierres atribuidos" in df.columns:
        total_cierres = df["Cierres atribuidos"].sum()
        cols_top[3].metric("🎯 Cierres atribuidos", f"{total_cierres:.1f}")

    st.markdown("")

    # Bar chart horizontal con gasto por conjunto
    fig = px.bar(
        df,
        x="Gasto USD",
        y="Conjunto",
        orientation="h",
        text="Gasto USD",
        color="Gasto USD",
        color_continuous_scale="Blues",
    )
    fig.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="outside",
    )
    fig.update_layout(
        height=max(280, 60 * len(df)),
        margin=dict(l=20, r=80, t=20, b=20),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        xaxis_title="Gasto (USD)",
        yaxis_title="",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabla detallada
    st.markdown("#### 📋 Detalle por conjunto")
    df_display = df.copy()
    df_display["Gasto USD"] = df_display["Gasto USD"].apply(lambda x: f"${x:,.2f}")
    if "Contactos" in df_display.columns:
        df_display["Contactos"] = df_display["Contactos"].apply(lambda x: f"{int(x):,}")
    if "Costo/contacto" in df_display.columns:
        df_display["Costo/contacto"] = df_display["Costo/contacto"].apply(
            lambda x: f"${x:,.2f}" if x else "—"
        )
    if "Impresiones" in df_display.columns:
        df_display["Impresiones"] = df_display["Impresiones"].apply(lambda x: f"{int(x):,}")
    if "Clics" in df_display.columns:
        df_display["Clics"] = df_display["Clics"].apply(lambda x: f"{int(x):,}")
    if "Costo/cierre" in df_display.columns:
        df_display["Costo/cierre"] = df_display["Costo/cierre"].apply(
            lambda x: f"${x:,.2f}" if x and x > 0 else "—"
        )
    if "Cierres atribuidos" in df_display.columns:
        df_display["Cierres atribuidos"] = df_display["Cierres atribuidos"].apply(
            lambda x: f"{x:.1f}" if x and x > 0 else "0"
        )

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.caption(
        f"Datos de Meta Ads ({len(df)} conjuntos activos en {year}-{month:02d}). "
        f"Cierres atribuidos proporcionalmente a los contactos generados por cada conjunto. "
        f"Útil para decidir a qué conjunto subir o bajar presupuesto."
    )
