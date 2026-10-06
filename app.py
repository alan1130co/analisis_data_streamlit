"""
Clientify Analyzer - punto de entrada Streamlit.

Ejecutar con:
    streamlit run app.py
"""
import time

import streamlit as st

from src.auth import check_password
from src.utils.sync_timing import log_marker, timed_stage
from src.config.settings import APP_TITLE
from src.ui.data_source_selector import render_data_source_selector
from src.ui.meta_ads_source import CSV_OPTION as META_CSV_OPTION
from src.ui.meta_ads_source import render_meta_ads_source
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
from src.ui.sections.pauta_vs_referidos_antiguedad import render_pauta_vs_referidos_antiguedad
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
from src.ui.sections.ad_spend import render_ad_spend, render_ad_spend_from_raw
from src.ui.sections.ad_spend_billed import API_MODE as BILLED_API_MODE
from src.ui.sections.ad_spend_billed import CSV_MODE as BILLED_CSV_MODE
from src.ui.sections.ad_spend_billed import render_ad_spend_billed
from src.ui.sections.ad_spend_vs_closures import render_ad_spend_vs_closures
from src.ui.sections.ad_spend_cost_per_lead import render_ad_spend_cost_per_lead
from src.ui.sections.ad_spend_vs_revenue import render_ad_spend_vs_revenue
from src.ui.sections.ad_spend_roas import render_ad_spend_roas
from src.ui.sections.ad_spend_total_roas import render_ad_spend_total_roas
from src.ui.sections.ad_spend_vs_process_value import render_ad_spend_vs_process_value
from src.ui.sections.ad_spend_vs_process_value_roas import render_ad_spend_vs_process_value_roas


def main():
    script_start = time.perf_counter()
    log_marker("################ main(): INICIO de rerun de Streamlit ################")
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

    # --- Facturación/Inversión de Meta Ads: NO depende de la fuente de
    # contactos de Clientify (Excel/API) — se carga y renderiza ANTES de
    # tocar `render_data_source_selector()` a propósito. Ese selector puede
    # bloquear el script varios minutos (sync completo de ~34k contactos
    # contra la API real, ver `src/ui/api_source.py`), y Streamlit ejecuta
    # el script de arriba hacia abajo en un solo hilo: cualquier `st.*` que
    # aparezca DESPUÉS de una llamada bloqueante no se pinta hasta que esa
    # llamada termina. Sin este reordenamiento, hasta el uploader de Meta
    # Ads y la gráfica "Gasto en pauta" (que no necesitan ni un contacto de
    # Clientify) se quedaban congelados detrás del spinner de sync.
    with st.sidebar:
        with timed_stage("render_meta_ads_source (Meta Ads, CSV o API)"):
            gasto_raw, meta_billing_files, meta_source = render_meta_ads_source()
        st.markdown("---")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Marketing e Inversión",
        "🧬 Segmentación Clave",
        "🔀 Embudo y Canales",
        "🧾 Gestión Comercial",
    ])

    # Esta parte de TAB 1 (gráfica "Gasto en pauta publicitaria") usa
    # ÚNICAMENTE `gasto_raw` (ya cargado arriba, sea por CSV o por la API de
    # Meta) — se renderiza YA, sin esperar a que la fuente de contactos
    # (elegida más abajo) termine de cargar. Las otras 6 gráficas de esta
    # pestaña SÍ cruzan gasto con leads/cierres de Clientify (reciben
    # `df_clientify` — confirmado en cada una de sus firmas), así que esas
    # quedan más abajo, después de que `df_unfiltered` exista.
    with tab1:
        if meta_source == META_CSV_OPTION:
            render_ad_spend(meta_billing_files)
            # Misma fuente CSV reutilizada tal cual (sin pedirla 2 veces) —
            # ambas gráficas mostrarían lo mismo, así que se omite la línea
            # de comparación (sería una diferencia trivial, siempre 0).
            render_ad_spend_billed(BILLED_CSV_MODE, csv_reuse_raw=gasto_raw)
        else:
            render_ad_spend_from_raw(gasto_raw)
            render_ad_spend_billed(BILLED_API_MODE, real_raw=gasto_raw)

    # --- Fuente de contactos de Clientify (Excel o API): puede bloquear el
    # script varios minutos si dispara un sync completo contra la API real.
    # Se pide DESPUÉS de todo lo que no depende de ella (ver comentario de
    # arriba). ---
    with st.sidebar:
        with timed_stage("render_data_source_selector (incluye fetch/cache de la fuente elegida)"):
            render_data_source_selector()
        st.divider()
        equipo = "todos"

    if st.session_state.df is None:
        with tab1:
            st.markdown("---")
            st.info(
                "👈 Elegí una fuente de datos de Clientify en el panel lateral "
                "para ver el cruce con leads/cierres en el resto de esta pestaña."
            )
        for tab in (tab2, tab3, tab4):
            with tab:
                st.info("👈 Elegí una fuente de datos en el panel lateral para comenzar el análisis.")
        log_marker(
            f"################ main(): FIN de rerun (sin fuente de datos) — "
            f"{time.perf_counter() - script_start:.2f} segundos totales ################"
        )
        return

    df_original = st.session_state.df
    df_unfiltered = df_original

    # df filtrado por equipo — solo para las secciones de detalle
    df = df_original.copy()

    # "Período de análisis" se movió al sidebar (antes vivía en el cuerpo
    # principal, arriba de los tabs). Con `st.tabs()` ahora creado ANTES de
    # cargar la fuente de contactos (ver más arriba), cualquier elemento de
    # nivel superior escrito acá con `st.*` aparecería DEBAJO de los 4 tabs
    # en vez de arriba — Streamlit ancla el widget de tabs en el punto donde
    # se llamó `st.tabs()`, y el flujo principal sigue después de él. El
    # sidebar no tiene ese problema (es un contenedor aparte), así que el
    # selector queda ahí, junto al resto de los controles de datos.
    with st.sidebar:
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

    with timed_stage("compute_all_metrics (período actual + anterior)"):
        metrics = compute_all_metrics(df_period_full, df_unfiltered)
        metrics_prev = compute_all_metrics(df_period_prev, df_unfiltered)

    # df filtrado para las secciones de detalle
    df_current = filter_by_month(df, selected)
    df_full = df

    # === TAB 1 (continuación): las 6 gráficas que SÍ cruzan gasto en pauta
    # con leads/cierres de Clientify — recién acá, con `df_unfiltered` ya
    # disponible ===
    with timed_stage("Render TAB 1 - gráficas gasto vs Clientify (6 gráficas)"):
        with tab1:
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
            st.markdown("---")
            render_ad_spend_vs_process_value(gasto_raw, df_unfiltered)
            st.markdown("---")
            render_ad_spend_vs_process_value_roas(gasto_raw, df_unfiltered)

    # === TAB 2: Segmentación Clave — quién cierra (geografía, demografía, proceso) ===
    with timed_stage("Render TAB 2 - Segmentación Clave"):
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
    with timed_stage("Render TAB 3 - Embudo y Canales"):
        with tab3:
            st.subheader("👤 Análisis por Asesor")
            render_funnel(df_full, selected.year, selected.month)
            st.markdown("---")
            periodo_pauta_referidos = render_pauta_vs_referidos(df, selected.year, selected.month, team=equipo)
            st.markdown("---")
            if periodo_pauta_referidos is not None:
                render_pauta_vs_referidos_antiguedad(df_full, *periodo_pauta_referidos)
                st.markdown("---")
            render_cierres_por_canal(df_full, selected.year, selected.month, team=equipo)
            st.markdown("---")
            render_closures_by_campaign(df_full, selected.year, selected.month, team=equipo)
            st.markdown("---")
            render_closures_by_publication(df_unfiltered, selected.year, selected.month)
            st.markdown("---")
            render_closures_by_channel_over_time(df_unfiltered)

    # === TAB 4: Gestión Comercial — KPIs, operación diaria, tendencias, detalle ===
    with timed_stage("Render TAB 4 - Gestión Comercial"):
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

    log_marker(
        f"################ main(): FIN de rerun (con datos) — "
        f"{time.perf_counter() - script_start:.2f} segundos totales ################"
    )


if __name__ == "__main__":
    main()
