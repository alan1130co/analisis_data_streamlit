"""
Clientify Analyzer - punto de entrada Streamlit.

Ejecutar con:
    streamlit run app.py
"""
import streamlit as st

from src.auth import check_password
from src.config.settings import APP_TITLE
from src.ui.upload import render_upload
from src.ui.kpi_cards import render_kpi_cards
from src.ui.styles import inject_custom_css
from src.analytics.metrics import compute_all_metrics, is_marketing
from src.analytics.filters import (
    filter_by_month,
    available_months,
    previous_month,
    default_month_index,
    format_month_label,
)

from src.ui.sections.pauta_vs_referidos import render_pauta_vs_referidos
from src.ui.sections.cierres_por_canal import render_cierres_por_canal
from src.ui.sections.closures_by_campaign import render_closures_by_campaign
from src.ui.sections.funnel import render_funnel
from src.ui.sections.daily_sales import render_daily_sales
from src.ui.sections.comparison import render_comparison
from src.ui.sections.trend import render_trend
from src.ui.sections.leads_summary import render_leads_summary
from src.ui.sections.no_closure_history import render_no_closure_history
from src.ui.sections.closures_by_process_type import render_closures_by_process_type
from src.ui.sections.closures_by_country import render_closures_by_country
from src.ui.sections.closures_by_state import render_closures_by_state
from src.ui.sections.closures_by_city import render_closures_by_city
from src.ui.sections.closures_by_sector import render_closures_by_sector
from src.ui.sections.closures_by_age import render_closures_by_age
from src.ui.sections.closures_by_publication import render_closures_by_publication
from src.ui.sections.closures_by_gender import render_closures_by_gender
from src.ui.sections.closures_vs_second_closures import render_closures_vs_second_closures
from src.ui.sections.closures_by_channel_over_time import render_closures_by_channel_over_time
from src.ui.sections.ad_spend import load_ad_spend_files, render_ad_spend
from src.ui.sections.ad_spend_vs_closures import render_ad_spend_vs_closures
from src.ui.sections.ad_spend_cost_per_lead import render_ad_spend_cost_per_lead
from src.ui.sections.ad_spend_vs_revenue import render_ad_spend_vs_revenue
from src.ui.sections.ad_spend_roas import render_ad_spend_roas
from src.ui.sections.ad_spend_total_roas import render_ad_spend_total_roas


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if not check_password():
        st.stop()

    inject_custom_css()

    st.title(APP_TITLE)
    st.caption("Dashboard comercial de Clientify — análisis de leads, calificaciones y cierres")

    if "df" not in st.session_state:
        st.session_state.df = None
        st.session_state.source_name = None

    with st.sidebar:
        st.header("Fuente de datos")
        source = st.radio(
            "¿De dónde cargar los datos?",
            options=["Archivo Excel", "API Clientify (próximamente)"],
            index=0,
        )

        if source == "Archivo Excel":
            df, source_name = render_upload()
            if df is not None:
                st.session_state.df = df
                st.session_state.source_name = source_name
        else:
            st.info("La integración con la API de Clientify se conectará aquí. Por ahora usá el Excel.")

        if st.session_state.df is not None:
            st.success(f"✅ Datos cargados: {st.session_state.source_name}")
            st.caption(f"{len(st.session_state.df):,} registros")
            if st.button("🔄 Cargar otro archivo", use_container_width=True):
                st.session_state.df = None
                st.session_state.source_name = None
                st.rerun()

        st.markdown("---")
        st.markdown("### 💰 Facturación / Inversión (Meta Ads)")
        meta_billing_files = st.file_uploader(
            "Cargar reportes de Facturación/Inversión (Meta Ads)",
            type=["csv", "xls", "xlsx"],
            key="meta_billing_uploader",
            accept_multiple_files=True,
            help=(
                "Podés cargar varios archivos a la vez: el histórico de "
                "facturación y los reportes nuevos de cada cuenta "
                "(columnas Fecha, Divisa, Importe)."
            ),
        )
        st.session_state.meta_billing_files = meta_billing_files

        st.divider()
        equipo = "todos"


    if st.session_state.df is None:
        st.info("👈 Cargá un archivo Excel desde el panel lateral para comenzar el análisis.")
        return

    df_original = st.session_state.df
    df_unfiltered = df_original

    # df filtrado por equipo — solo para las secciones de detalle
    df = df_original.copy()

    months = available_months(df_unfiltered)
    selected = st.selectbox(
        "Período de análisis",
        options=months,
        index=default_month_index(months),
        format_func=lambda m: format_month_label(m),
    )

    # Métricas siempre sobre el dataset completo — los campos internos ya separan pauta/referido
    df_period_full = filter_by_month(df_unfiltered, selected)
    prev = previous_month(selected)
    df_period_prev = filter_by_month(df_unfiltered, prev)

    metrics = compute_all_metrics(df_period_full, df_unfiltered)
    metrics_prev = compute_all_metrics(df_period_prev, df_unfiltered)

    # df filtrado para las secciones de detalle
    df_current = filter_by_month(df, selected)
    df_full = df

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Marketing e Inversión",
        "🧬 Segmentación Clave",
        "🔀 Embudo y Canales",
        "🧾 Gestión Comercial",
    ])

    # === TAB 1: Marketing e Inversión — gasto en pauta, costo por lead, ROAS ===
    with tab1:
        meta_billing_files = st.session_state.get("meta_billing_files")
        gasto_raw = load_ad_spend_files(meta_billing_files)
        render_ad_spend(meta_billing_files)
        st.markdown("---")
        render_ad_spend_vs_closures(gasto_raw, df_unfiltered)
        st.markdown("---")
        render_ad_spend_cost_per_lead(gasto_raw, df_unfiltered)
        st.markdown("---")
        render_ad_spend_vs_revenue(gasto_raw, df_unfiltered)
        st.markdown("---")
        render_ad_spend_roas(gasto_raw, df_unfiltered)
        st.markdown("---")
        render_ad_spend_total_roas(gasto_raw, df_unfiltered)

    # === TAB 2: Segmentación Clave — quién cierra (geografía, demografía, proceso) ===
    with tab2:
        render_closures_by_process_type(df, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_country(df, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_state(df, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_city(df, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_sector(df, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_age(df, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_gender(df, selected.year, selected.month)

    # === TAB 3: Embudo y Canales — de dónde entran los leads y cómo avanzan ===
    with tab3:
        st.subheader("👤 Análisis por Asesor")
        render_funnel(df_current, df_full, selected.year, selected.month)
        st.markdown("---")
        render_pauta_vs_referidos(df_current, df, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_cierres_por_canal(df_current, df_full, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_campaign(df_full, selected.year, selected.month, team=equipo)
        st.markdown("---")
        render_closures_by_publication(df_unfiltered, selected.year, selected.month)
        st.markdown("---")
        render_closures_by_channel_over_time(df_unfiltered)

    # === TAB 4: Gestión Comercial — KPIs, operación diaria, tendencias, detalle ===
    with tab4:
        render_kpi_cards(metrics, metrics_prev=metrics_prev, team=equipo)
        st.markdown("---")
        render_closures_vs_second_closures(df_unfiltered)
        st.markdown("---")
        render_daily_sales(df_full, selected)
        st.markdown("---")
        render_no_closure_history(df_unfiltered, default_year=selected.year, default_month=selected.month)
        st.markdown("---")
        render_comparison(df_unfiltered, selected)
        st.markdown("---")
        render_trend(df_unfiltered, default_month=selected)
        st.markdown("---")
        render_leads_summary(df_unfiltered, default_month=selected)

        with st.expander("Ver datos del período"):
            # Las columnas "_is_*" son derivadas internas precalculadas por
            # precompute_derived_columns (ver src/ui/upload.py) para acelerar los
            # cálculos — no son datos del Excel original, no deben mostrarse acá.
            cols_visibles = [c for c in df_current.columns if not c.startswith("_is_")]
            st.dataframe(df_current[cols_visibles], use_container_width=True)


if __name__ == "__main__":
    main()
