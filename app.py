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
from src.analytics.filters import filter_by_month, available_months, previous_month

from src.ui.sections.pauta_vs_referidos import render_pauta_vs_referidos
from src.ui.sections.cierres_por_canal import render_cierres_por_canal
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
from src.ui.sections.investment_by_set import render_investment_by_set
from src.ui.sections.cp_attribution import render_cp_attribution


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
        st.markdown("### 📊 Conjuntos de anuncios (opcional)")
        meta_sets_file = st.file_uploader(
            "Cargar CSV de Conjuntos de Meta",
            type=["csv"],
            key="meta_sets_uploader",
            help="Export del reporte 'Conjuntos de anuncios' desde Meta Ads Manager.",
        )

        df_meta_sets = None
        if meta_sets_file is not None:
            from src.data_sources.meta_sets_loader import MetaSetsLoader
            try:
                df_meta_sets = MetaSetsLoader(meta_sets_file).load()
                st.success(f"✅ {len(df_meta_sets)} conjuntos cargados")
            except Exception as e:
                st.error(f"Error al cargar el CSV: {e}")

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎯 Atribución REAL (CP de Meta)")
        cp_files = st.sidebar.file_uploader(
            "Cargar CSV de CP de Meta (varios archivos)",
            type=["csv"],
            key="cp_uploader",
            accept_multiple_files=True,  # ← CRUCIAL: permite múltiples
            help="Descargá desde Meta Ads Manager → Conjuntos → cada Video → Descargar CP. Subí todos juntos.",
        )

        df_cp = None
        if cp_files:
            from src.data_sources.meta_cp_loader import MetaCPLoader
            try:
                df_cp = MetaCPLoader(cp_files).load()
                st.sidebar.success(f"✅ {len(df_cp)} CP cargados de {len(cp_files)} archivos")
            except Exception as e:
                st.sidebar.error(f"Error al cargar CP: {e}")

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
        index=0,
        format_func=lambda m: m.strftime("%B %Y").capitalize(),
    )

    # Métricas siempre sobre el dataset completo — los campos internos ya separan pauta/referido
    df_period_full = filter_by_month(df_unfiltered, selected)
    prev = previous_month(selected)
    df_period_prev = filter_by_month(df_unfiltered, prev)

    metrics = compute_all_metrics(df_period_full, df_unfiltered)
    metrics_prev = compute_all_metrics(df_period_prev, df_unfiltered)

    render_kpi_cards(metrics, metrics_prev=metrics_prev, team=equipo)

    # df filtrado para las secciones de detalle
    df_current = filter_by_month(df, selected)
    df_full = df

    # --- Análisis detallado ---
    st.markdown("---")
    st.header("Análisis detallado")

    # Secciones que respetan filtro de equipo
    render_pauta_vs_referidos(df_current, df, team=equipo)
    st.markdown("---")
    render_cierres_por_canal(df_current, df_full, team=equipo)
    st.markdown("---")
    render_funnel(df_current, df_full)
    st.markdown("---")
    render_daily_sales(df_full, selected)

    # Secciones globales (no respetan filtro de equipo)
    st.markdown("---")
    render_comparison(df_unfiltered, selected)
    st.markdown("---")
    render_trend(df_unfiltered, default_month=selected)
    st.markdown("---")
    render_leads_summary(df_unfiltered, default_month=selected)
    st.markdown("---")
    render_no_closure_history(df_unfiltered, default_year=selected.year, default_month=selected.month)

    st.markdown("---")
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
    render_closures_by_gender(df, selected.year, selected.month, team=equipo)

    st.markdown("---")
    render_closures_by_publication(df_unfiltered, selected.year, selected.month)

    st.markdown("---")
    render_investment_by_set(df_meta_sets, df, selected.year, selected.month)

    st.markdown("---")
    render_cp_attribution(df_cp, df, selected.year, selected.month)

    with st.expander("Ver datos del período"):
        st.dataframe(df_current, use_container_width=True)


if __name__ == "__main__":
    main()
