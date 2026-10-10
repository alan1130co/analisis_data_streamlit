"""Botones "Generar reporte" — uno por pestaña (Marketing, Segmentación,
Embudo, Gestión Comercial, ver `render_report_generator`) más el de
"Reporte completo" en el sidebar (`render_full_report_generator`).
Arquitectura declarativa por secciones (`src/reports/section_registry.py`)
— agregar una 5ta pestaña con reporte no toca este archivo.

Cada botón entrega PDF (imágenes vía matplotlib, nunca kaleido/Chromium,
ver `src/reports/chart_builder_matplotlib*.py`) como descarga PRINCIPAL;
Marketing además ofrece HTML interactivo (Plotly) como descarga
SECUNDARIA/opcional (es la única sección con figuras Plotly ya existentes,
ver `src/reports/chart_builder.py`). Nombre de archivo con sección y
fecha. El último reporte generado por sección se guarda en
`st.session_state` (no se regenera, ni se vuelve a pagar la IA, al
interactuar con otros widgets de la página).

Costo: ESTIMADO antes de generar (`estimate_section_cost_usd`/
`estimate_combined_report_cost_usd` — aproximado, ver esas funciones en
`report_orchestrator.py`) y REAL después de generar (tokens reales
devueltos por la API, ver `generate_with_usage` en `ai_provider.py`). El
análisis de IA en sí se cachea por hash del payload.

Cada `render_*` está decorado con `@st.fragment`: generar un reporte NO
dispara un rerun completo de la app (no se re-sincroniza Meta Ads/Clientify
ni se re-renderizan las otras pestañas).
"""
from __future__ import annotations

import dataclasses

import pandas as pd
import streamlit as st

from src.analytics.ad_spend import TODOS, anios_disponibles, monthly_ad_spend_with_period
from src.config.settings import APP_TIMEZONE
from src.data_sources.ai_provider import check_ai_connection, get_ai_provider
from src.reports.chart_builder import build_figures_by_group as build_marketing_figures_plotly
from src.reports.pdf_report import build_full_pdf_report, build_html_report, build_pdf_report
from src.reports.report_orchestrator import (
    estimate_combined_report_cost_usd,
    estimate_section_cost_usd,
    generate_combined_report_analysis,
    generate_section_analysis,
    payload_hash,
)
from src.reports.section_registry import SECTIONS, SECTIONS_ORDEN
from src.reports.section_types import ReportContext

_SESSION_KEY_REPORT_PREFIX = "reporte_generado__"
_SESSION_KEY_ANALYSIS_CACHE_PREFIX = "reporte_analisis_cache__"
_SESSION_KEY_REPORT_COMPLETO = "reporte_completo_generado"
_SESSION_KEY_ANALYSIS_CACHE_COMPLETO = "reporte_completo_analisis_cache"


def _anio_actual() -> int:
    return pd.Timestamp.now(tz=APP_TIMEZONE).year


def _periodo_options_marketing(gasto_raw: pd.DataFrame) -> list:
    if gasto_raw is None or gasto_raw.empty:
        return [TODOS]
    meses = list(monthly_ad_spend_with_period(gasto_raw)["Mes_Año"])
    return [TODOS] + anios_disponibles(meses)


def _secciones_fallidas(grupos_titulos: dict[str, str], analisis_grupos: dict[str, str], resumen: str) -> list[str]:
    """Títulos de los grupos (+ el resumen ejecutivo) cuyo análisis de IA
    falló — usado para avisar con `st.warning` sin un "no disponible"
    silencioso (el motivo exacto ya queda en el PDF)."""
    fallidas = [titulo for gid, titulo in grupos_titulos.items() if "Análisis no disponible" in analisis_grupos.get(gid, "")]
    if "Análisis no disponible" in resumen:
        fallidas.append("Resumen ejecutivo")
    return fallidas


@st.fragment
def render_report_generator(section_id: str, ctx: ReportContext, periodo_label: str) -> None:
    """Botón "Generar reporte" de UNA sección/pestaña.

    `ctx`: contexto ya armado por `app.py` para el período/equipo
    actualmente seleccionado (ver `src/reports/section_types.py`).
    `periodo_label`: texto a mostrar como "Período analizado" en el PDF
    (p.ej. "Marzo 2026")."""
    spec = SECTIONS[section_id]
    session_report_key = f"{_SESSION_KEY_REPORT_PREFIX}{section_id}"
    session_cache_key = f"{_SESSION_KEY_ANALYSIS_CACHE_PREFIX}{section_id}"

    st.markdown(f"#### 📄 Generar reporte de {spec.title}")

    if not spec.data_available(ctx):
        st.info(spec.no_data_message)
        return

    provider = get_ai_provider()
    if provider is None:
        st.button("Generar reporte", disabled=True, key=f"btn_generar_reporte_{section_id}")
        st.caption("Configura AI_API_KEY para generar el reporte")
        return

    if st.button("🔌 Probar conexión con la IA", key=f"btn_probar_conexion_ia_{section_id}"):
        with st.spinner("Probando conexión..."):
            ok, mensaje = check_ai_connection(provider)
        if ok:
            st.success(mensaje)
        else:
            st.error(f"Error de IA: {mensaje}")

    anio_filter = ctx.anio_filter
    if section_id == "marketing":
        opciones_periodo = _periodo_options_marketing(ctx.gasto_raw)
        anio_actual = _anio_actual()
        index_default = opciones_periodo.index(anio_actual) if anio_actual in opciones_periodo else 0
        anio_filter = st.selectbox(
            "Período del reporte", options=opciones_periodo, index=index_default,
            key=f"reporte_periodo_sel_{section_id}",
        )
        ctx = dataclasses.replace(ctx, anio_filter=anio_filter)
        periodo_label = "Todos los períodos" if anio_filter == TODOS else str(anio_filter)
    else:
        st.caption(f"Período analizado: {periodo_label}")

    grupos_payload = {g.id: g.payload_builder(ctx) for g in spec.groups}
    payload = {"periodo": periodo_label, "grupos": grupos_payload}
    hash_actual = payload_hash(payload)

    costo_estimado = estimate_section_cost_usd(provider, spec, payload)
    st.caption(f"💰 Costo estimado de este reporte: ${costo_estimado:.4f} USD (aprox., antes de generar)")

    if st.button("Generar reporte", key=f"btn_generar_reporte_{section_id}"):
        cache = st.session_state.get(session_cache_key, {})
        if cache.get("hash") == hash_actual:
            analisis = cache["analisis"]
        else:
            total_pasos = len(spec.groups) + 1
            progreso = st.progress(0.0, text="Preparando análisis...")

            def _on_progress(indice: int, total: int, descripcion: str) -> None:
                progreso.progress(indice / total, text=f"Analizando {indice} de {total}: {descripcion}")

            analisis = generate_section_analysis(provider, spec, payload, on_progress=_on_progress)
            progreso.empty()
            st.session_state[session_cache_key] = {"hash": hash_actual, "analisis": analisis}

        fallidas = _secciones_fallidas(spec.group_titles, analisis["grupos"], analisis["resumen_ejecutivo"])
        if fallidas:
            st.warning(
                "⚠️ El análisis de IA no se pudo generar para: " + ", ".join(fallidas) +
                " — el reporte incluye el motivo exacto en cada sección afectada."
            )

        fecha_str = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d")
        titulo_portada = f"Reporte de {spec.title}"

        with st.spinner("Armando el PDF..."):
            figuras_mpl_por_grupo = spec.figures_builder(ctx)
            grupos_doc_pdf = [
                {
                    "titulo": g.title,
                    "figuras": figuras_mpl_por_grupo.get(g.id, []),
                    "analisis": analisis["grupos"].get(g.id, "Análisis no disponible."),
                }
                for g in spec.groups
            ]
            pdf_bytes = build_pdf_report(
                periodo_label=periodo_label, resumen_ejecutivo=analisis["resumen_ejecutivo"],
                grupos=grupos_doc_pdf, titulo_portada=titulo_portada,
            )

        reporte = {
            "pdf_bytes": pdf_bytes,
            "pdf_nombre": f"reporte_{section_id}_{fecha_str}.pdf",
            "costo_real_usd": analisis.get("costo_real_usd", 0.0),
        }

        # Marketing es la única sección con figuras Plotly ya existentes
        # (`chart_builder.py`) — las demás solo ofrecen PDF.
        if section_id == "marketing":
            figuras_plotly_por_grupo = build_marketing_figures_plotly(ctx.gasto_raw, ctx.df_clientify, ctx.billed_raw, anio_filter)
            grupos_doc_html = [
                {
                    "titulo": g.title,
                    "figuras": figuras_plotly_por_grupo.get(g.id, []),
                    "analisis": analisis["grupos"].get(g.id, "Análisis no disponible."),
                }
                for g in spec.groups
            ]
            html_str = build_html_report(
                periodo_label=periodo_label, resumen_ejecutivo=analisis["resumen_ejecutivo"],
                grupos=grupos_doc_html, titulo_portada=titulo_portada,
            )
            reporte["html_bytes"] = html_str.encode("utf-8")
            reporte["html_nombre"] = f"reporte_{section_id}_{fecha_str}.html"

        st.session_state[session_report_key] = reporte

    reporte = st.session_state.get(session_report_key)
    if reporte:
        st.caption(f"💵 Costo real de la última generación: ${reporte.get('costo_real_usd', 0.0):.4f} USD")
        st.download_button(
            "⬇️ Descargar reporte (PDF)", data=reporte["pdf_bytes"], file_name=reporte["pdf_nombre"],
            mime="application/pdf", key=f"btn_descargar_reporte_pdf_{section_id}",
        )
        if "html_bytes" in reporte:
            st.download_button(
                "⬇️ Descargar versión interactiva (HTML, opcional)", data=reporte["html_bytes"],
                file_name=reporte["html_nombre"], mime="text/html", key=f"btn_descargar_reporte_html_{section_id}",
            )


@st.fragment
def render_full_report_generator(ctx: ReportContext, periodo_label: str) -> None:
    """Botón "Reporte completo" (sidebar) — las 4 secciones en un solo PDF
    con portada, índice, resumen ejecutivo global y Top 5 prioridades (ver
    `src/reports/pdf_report.py::build_full_pdf_report`). Una sección sin
    datos cargados se omite con una nota, sin romper el resto."""
    st.markdown("#### 📄 Reporte completo (todas las pestañas)")

    provider = get_ai_provider()
    if provider is None:
        st.button("Generar reporte completo", disabled=True, key="btn_generar_reporte_completo")
        st.caption("Configura AI_API_KEY para generar el reporte")
        return

    payloads_by_section: dict[str, dict] = {}
    for sid in SECTIONS_ORDEN:
        spec = SECTIONS[sid]
        if not spec.data_available(ctx):
            st.info(f"{spec.title}: {spec.no_data_message} (se omite del reporte completo)")
            continue
        grupos_payload = {g.id: g.payload_builder(ctx) for g in spec.groups}
        payloads_by_section[sid] = {"periodo": periodo_label, "grupos": grupos_payload}

    if not payloads_by_section:
        st.warning("No hay datos disponibles en ninguna sección todavía.")
        return

    hash_actual = payload_hash({"secciones": payloads_by_section})
    costo_estimado = estimate_combined_report_cost_usd(provider, payloads_by_section)
    st.caption(f"💰 Costo estimado del reporte completo: ${costo_estimado:.4f} USD (aprox., antes de generar)")

    if st.button("Generar reporte completo", key="btn_generar_reporte_completo"):
        cache = st.session_state.get(_SESSION_KEY_ANALYSIS_CACHE_COMPLETO, {})
        if cache.get("hash") == hash_actual:
            analisis = cache["analisis"]
        else:
            secciones_incluidas = [sid for sid in SECTIONS_ORDEN if sid in payloads_by_section]
            total_pasos = sum(len(SECTIONS[sid].groups) for sid in secciones_incluidas) + 1
            progreso = st.progress(0.0, text="Preparando análisis...")

            def _on_progress(indice: int, total: int, descripcion: str) -> None:
                progreso.progress(indice / total, text=f"Analizando {indice} de {total}: {descripcion}")

            analisis = generate_combined_report_analysis(provider, payloads_by_section, on_progress=_on_progress)
            progreso.empty()
            st.session_state[_SESSION_KEY_ANALYSIS_CACHE_COMPLETO] = {"hash": hash_actual, "analisis": analisis}

        fecha_str = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d")
        with st.spinner("Armando el PDF..."):
            secciones_doc = []
            for sid in SECTIONS_ORDEN:
                spec = SECTIONS[sid]
                if sid not in payloads_by_section:
                    secciones_doc.append({"titulo": spec.title, "sin_datos": True, "nota_sin_datos": spec.no_data_message})
                    continue
                figuras_por_grupo = spec.figures_builder(ctx)
                analisis_grupos = analisis["analisis_por_seccion"].get(sid, {})
                secciones_doc.append({
                    "titulo": spec.title,
                    "grupos": [
                        {
                            "titulo": g.title,
                            "figuras": figuras_por_grupo.get(g.id, []),
                            "analisis": analisis_grupos.get(g.id, "Análisis no disponible."),
                        }
                        for g in spec.groups
                    ],
                })
            pdf_bytes = build_full_pdf_report(
                periodo_label=periodo_label, resumen_ejecutivo_global=analisis["resumen_ejecutivo_global"],
                secciones=secciones_doc,
            )

        st.session_state[_SESSION_KEY_REPORT_COMPLETO] = {
            "pdf_bytes": pdf_bytes,
            "pdf_nombre": f"reporte_completo_{fecha_str}.pdf",
            "costo_real_usd": analisis.get("costo_real_usd", 0.0),
            "secciones_omitidas": analisis.get("secciones_omitidas", []),
        }

    reporte = st.session_state.get(_SESSION_KEY_REPORT_COMPLETO)
    if reporte:
        if reporte["secciones_omitidas"]:
            omitidas = ", ".join(SECTIONS[sid].title for sid in reporte["secciones_omitidas"])
            st.info(f"Secciones omitidas por falta de datos: {omitidas}")
        st.caption(f"💵 Costo real de la última generación: ${reporte.get('costo_real_usd', 0.0):.4f} USD")
        st.download_button(
            "⬇️ Descargar reporte completo (PDF)", data=reporte["pdf_bytes"], file_name=reporte["pdf_nombre"],
            mime="application/pdf", key="btn_descargar_reporte_completo_pdf",
        )
