"""Orquestador de llamadas a la IA para el análisis de los reportes PDF —
1 llamada por GRUPO de gráficas más una llamada final de resumen ejecutivo,
ejecutadas EN PARALELO (`ThreadPoolExecutor`, máx. `MAX_WORKERS` a la vez)
para que un reporte de varios grupos no tarde la suma de todas las llamadas.
Si una llamada falla, esa sección queda con una nota de "Análisis no
disponible" — el reporte se genera igual, nunca se aborta todo por una sola
llamada fallida.

`generate_full_report_analysis` (Marketing, firma histórica) se mantiene
intacta por compatibilidad con sus tests/UI existentes — por debajo ya
corre en paralelo, delegando en `generate_section_analysis` (genérica,
usada también por Segmentación/Embudo/Gestión Comercial vía
`src/reports/section_registry.py`) y en el "reporte completo"
(`generate_combined_report_analysis`, todas las secciones disponibles a la
vez + 1 resumen ejecutivo global).

NO importa Streamlit — el progreso se reporta vía un callback opcional
(`on_progress`), no vía `st.progress` directamente.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import logging
from typing import Callable

from src.config.report_prompts import (
    EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
    GLOBAL_EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
    build_executive_summary_user_prompt,
    build_global_executive_summary_user_prompt,
    build_group_system_prompt,
    build_group_user_prompt,
)
from src.data_sources.ai_provider import (
    MAX_OUTPUT_TOKENS,
    AIProvider,
    AIProviderError,
    estimate_cost_usd,
    estimate_tokens,
)

logger = logging.getLogger(__name__)

MAX_WORKERS = 4

ANALISIS_NO_DISPONIBLE = (
    "**Análisis no disponible**: no se pudo generar el análisis de IA para "
    "este grupo. Revisá las cifras y gráficas de esta sección manualmente."
)

_SIN_USO = {"input_tokens": 0, "output_tokens": 0}


def _nota_no_disponible(motivo: str) -> str:
    """Nota de "no disponible" CON el motivo real sanitizado (nunca la API
    key — ya viene limpio desde `AIProviderError`) — antes el reporte y la
    UI mostraban `ANALISIS_NO_DISPONIBLE` (genérico, sin ninguna pista de
    qué falló: saldo insuficiente, modelo inválido, timeout, etc.), lo que
    hacía casi imposible diagnosticarlo sin mirar los logs del servidor."""
    return f"{ANALISIS_NO_DISPONIBLE}\n\n**Motivo**: {motivo}"


def payload_hash(payload: dict) -> str:
    """Hash estable del payload — usado para cachear el análisis por
    sesión (no regenerar, no volver a pagar, si el payload no cambió)."""
    serializado = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def generate_group_analysis(
    provider: AIProvider, group_title: str, group_payload: dict, business_context: str,
) -> tuple[str, dict]:
    """Genera el análisis de UN grupo dado su TÍTULO y el contexto de
    negocio de SU SECCIÓN (cualquier sección puede llamarlo, no solo
    Marketing — ver `BUSINESS_CONTEXT_*` en `report_prompts.py`). Nunca
    lanza — si la llamada falla devuelve `ANALISIS_NO_DISPONIBLE` + el
    motivo sanitizado (uso en cero) y loguea el error (ya sanitizado sin la
    API key, ver `AIProviderError`)."""
    system_prompt = build_group_system_prompt(group_title, business_context)
    user_prompt = build_group_user_prompt(json.dumps(group_payload, ensure_ascii=False, default=str))
    try:
        return _generate_with_usage(provider, system_prompt, user_prompt)
    except AIProviderError as exc:
        logger.warning("Análisis de IA falló para el grupo '%s': %s", group_title, exc)
        return _nota_no_disponible(str(exc)), dict(_SIN_USO)


def _generate_with_usage(provider: AIProvider, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    """Igual que `provider.generate_with_usage(...)`, pero tolerante con
    dobles de test/adaptadores mínimos que solo implementan `generate()`
    (sin heredar de `AIProvider`, que es donde vive el default) — evita que
    el orquestador les exija un método que no tienen."""
    if hasattr(provider, "generate_with_usage"):
        return provider.generate_with_usage(system_prompt, user_prompt)
    return provider.generate(system_prompt, user_prompt), dict(_SIN_USO)


def generate_executive_summary(provider: AIProvider, group_analyses_by_title: dict[str, str]) -> tuple[str, dict]:
    """Resumen ejecutivo de UNA sección a partir de los análisis YA
    generados por grupo (nunca recibe el payload crudo de nuevo)."""
    user_prompt = build_executive_summary_user_prompt(group_analyses_by_title)
    try:
        return _generate_with_usage(provider, EXECUTIVE_SUMMARY_SYSTEM_PROMPT, user_prompt)
    except AIProviderError as exc:
        logger.warning("Resumen ejecutivo de IA falló: %s", exc)
        return _nota_no_disponible(str(exc)), dict(_SIN_USO)


def generate_global_executive_summary(provider: AIProvider, analyses_by_section_and_title: dict) -> tuple[str, dict]:
    """Resumen ejecutivo GLOBAL del "reporte completo" — integra los
    análisis ya generados de las N secciones disponibles + Top 5
    prioridades con responsable sugerido y plazo (ver `report_prompts.py`)."""
    user_prompt = build_global_executive_summary_user_prompt(analyses_by_section_and_title)
    try:
        return _generate_with_usage(provider, GLOBAL_EXECUTIVE_SUMMARY_SYSTEM_PROMPT, user_prompt)
    except AIProviderError as exc:
        logger.warning("Resumen ejecutivo global de IA falló: %s", exc)
        return _nota_no_disponible(str(exc)), dict(_SIN_USO)


def generate_groups_analysis_parallel(
    provider: AIProvider,
    groups: list[tuple],
    on_progress: Callable[[int, int, str], None] | None = None,
    max_workers: int = MAX_WORKERS,
    total_steps: int | None = None,
) -> tuple[dict, dict]:
    """Corre 1 llamada de IA por grupo, hasta `max_workers` en paralelo
    (`ThreadPoolExecutor`) — nunca aborta si una falla (ver
    `generate_group_analysis`). `groups`: lista de `(group_key, titulo,
    payload, business_context)` — `group_key` puede ser cualquier valor
    hasheable (un `group_id` de sección, o un `(section_id, group_id)` para
    el reporte completo); `business_context` es el de LA SECCIÓN a la que
    pertenece ese grupo (distinto grupo a grupo en el reporte completo,
    donde se mezclan secciones).

    `on_progress` se llama en ORDEN DE SUBMISIÓN (1..N), no de finalización
    — así la barra de progreso de la UI siempre avanza hacia adelante,
    aunque por debajo las llamadas terminen en otro orden al correr en
    paralelo.

    Devuelve `(resultados, uso_total)` — `resultados`: `{group_key: texto}`;
    `uso_total`: `{"input_tokens": int, "output_tokens": int}` sumado de
    TODAS las llamadas (para el costo real del reporte)."""
    total_steps = total_steps if total_steps is not None else len(groups)
    resultados: dict = {}
    uso_total = dict(_SIN_USO)

    with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(generate_group_analysis, provider, titulo, payload, business_context)
            for (_, titulo, payload, business_context) in groups
        ]
        for i, ((group_key, titulo, _, _bc), future) in enumerate(zip(groups, futures), start=1):
            if on_progress is not None:
                on_progress(i, total_steps, titulo)
            texto, uso = future.result()
            resultados[group_key] = texto
            uso_total["input_tokens"] += uso.get("input_tokens", 0)
            uso_total["output_tokens"] += uso.get("output_tokens", 0)

    return resultados, uso_total


def _costo_real(provider: AIProvider, *usages: dict) -> float:
    total_in = sum(u.get("input_tokens", 0) for u in usages)
    total_out = sum(u.get("output_tokens", 0) for u in usages)
    return estimate_cost_usd(getattr(provider, "provider_name", "anthropic"), getattr(provider, "model", ""), total_in, total_out)


def generate_section_analysis(
    provider: AIProvider,
    section_spec,
    payload: dict,
    on_progress: Callable[[int, int, str], None] | None = None,
    max_workers: int = MAX_WORKERS,
) -> dict:
    """Versión GENÉRICA de "1 llamada por grupo + 1 resumen ejecutivo" para
    CUALQUIER `SectionSpec` (ver `src/reports/section_types.py`) — Marketing,
    Segmentación, Embudo o Gestión Comercial. Devuelve
    `{"resumen_ejecutivo": str, "grupos": {group_id: str}, "costo_real_usd":
    float, "tokens_reales": {...}}`."""
    grupos_payload = payload.get("grupos", {})
    groups = [
        (g.id, g.title, grupos_payload.get(g.id, {}), section_spec.business_context)
        for g in section_spec.groups
    ]
    total_llamadas = len(groups) + 1

    analisis_por_grupo, uso_grupos = generate_groups_analysis_parallel(
        provider, groups, on_progress=on_progress, max_workers=max_workers, total_steps=total_llamadas,
    )

    if on_progress is not None:
        on_progress(total_llamadas, total_llamadas, "Resumen ejecutivo")
    analisis_por_titulo = {g.title: analisis_por_grupo.get(g.id, "") for g in section_spec.groups}
    resumen_ejecutivo, uso_resumen = generate_executive_summary(provider, analisis_por_titulo)

    uso_total = {
        "input_tokens": uso_grupos["input_tokens"] + uso_resumen["input_tokens"],
        "output_tokens": uso_grupos["output_tokens"] + uso_resumen["output_tokens"],
    }
    return {
        "resumen_ejecutivo": resumen_ejecutivo,
        "grupos": analisis_por_grupo,
        "costo_real_usd": _costo_real(provider, uso_grupos, uso_resumen),
        "tokens_reales": uso_total,
    }


def generate_full_report_analysis(
    provider: AIProvider,
    payload: dict,
    on_progress: Callable[[int, int, str], None] | None = None,
    max_workers: int = MAX_WORKERS,
) -> dict:
    """Firma histórica (Marketing) — se mantiene por compatibilidad con la
    UI/tests existentes. Por debajo delega en `generate_section_analysis`
    con la sección "marketing" del registro (ver
    `src/reports/section_registry.py`), así que ya corre en paralelo."""
    from src.reports.section_registry import SECTIONS

    return generate_section_analysis(provider, SECTIONS["marketing"], payload, on_progress=on_progress, max_workers=max_workers)


def generate_combined_report_analysis(
    provider: AIProvider,
    payloads_by_section: dict[str, dict],
    on_progress: Callable[[int, int, str], None] | None = None,
    max_workers: int = MAX_WORKERS,
) -> dict:
    """"Reporte completo": corre TODOS los grupos de TODAS las secciones con
    datos disponibles en paralelo (hasta `max_workers` a la vez, sin
    importar a qué sección pertenezca cada grupo) + 1 resumen ejecutivo
    GLOBAL final que integra las secciones y prioriza acciones.

    `payloads_by_section`: `{section_id: payload}` — SOLO las secciones con
    datos cargados (ver `SectionSpec.data_available`); las que falten
    quedan en `"secciones_omitidas"` del resultado, sin abortar el resto.

    El orden de `"secciones_incluidas"` respeta `SECTIONS_ORDEN`, sin
    importar en qué orden terminen las llamadas en paralelo."""
    from src.reports.section_registry import SECTIONS, SECTIONS_ORDEN

    secciones_incluidas = [sid for sid in SECTIONS_ORDEN if sid in payloads_by_section]
    secciones_omitidas = [sid for sid in SECTIONS_ORDEN if sid not in payloads_by_section]

    groups: list[tuple[tuple[str, str], str, dict, str]] = []
    for sid in secciones_incluidas:
        spec = SECTIONS[sid]
        grupos_payload = payloads_by_section[sid].get("grupos", {})
        for g in spec.groups:
            groups.append(((sid, g.id), f"[{spec.title}] {g.title}", grupos_payload.get(g.id, {}), spec.business_context))

    total_llamadas = len(groups) + 1
    resultados_por_clave, uso_grupos = generate_groups_analysis_parallel(
        provider, groups, on_progress=on_progress, max_workers=max_workers, total_steps=total_llamadas,
    )

    analisis_por_seccion: dict[str, dict[str, str]] = {sid: {} for sid in secciones_incluidas}
    for (sid, gid), _titulo, _payload, _bc in groups:
        analisis_por_seccion[sid][gid] = resultados_por_clave[(sid, gid)]

    if on_progress is not None:
        on_progress(total_llamadas, total_llamadas, "Resumen ejecutivo global")

    analisis_para_resumen_global = {
        SECTIONS[sid].title: {
            SECTIONS[sid].group_titles[gid]: texto for gid, texto in analisis_por_seccion[sid].items()
        }
        for sid in secciones_incluidas
    }
    resumen_global, uso_resumen = generate_global_executive_summary(provider, analisis_para_resumen_global)

    uso_total = {
        "input_tokens": uso_grupos["input_tokens"] + uso_resumen["input_tokens"],
        "output_tokens": uso_grupos["output_tokens"] + uso_resumen["output_tokens"],
    }
    return {
        "secciones_incluidas": secciones_incluidas,
        "secciones_omitidas": secciones_omitidas,
        "resumen_ejecutivo_global": resumen_global,
        "analisis_por_seccion": analisis_por_seccion,
        "costo_real_usd": _costo_real(provider, uso_grupos, uso_resumen),
        "tokens_reales": uso_total,
    }


def _estimate_tokens_for_groups(groups: list[tuple[str, dict, str]]) -> tuple[int, int]:
    """(tokens_entrada, tokens_salida) estimados para 1 llamada por grupo —
    SIN el resumen ejecutivo final (se suma aparte, ver callers). `groups`:
    `(titulo, payload, business_context)`."""
    total_in = 0
    total_out = 0
    for titulo, payload, business_context in groups:
        system_prompt = build_group_system_prompt(titulo, business_context)
        user_prompt = build_group_user_prompt(json.dumps(payload, ensure_ascii=False, default=str))
        total_in += estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
        total_out += MAX_OUTPUT_TOKENS
    return total_in, total_out


def estimate_section_cost_usd(provider: AIProvider, section_spec, payload: dict) -> float:
    """Costo ESTIMADO (ANTES de llamar a la IA) de generar el análisis
    completo de una sección — ver `estimate_tokens`/`estimate_cost_usd` en
    `ai_provider.py` para las limitaciones de la estimación."""
    grupos_payload = payload.get("grupos", {})
    groups = [(g.title, grupos_payload.get(g.id, {}), section_spec.business_context) for g in section_spec.groups]
    tokens_in, tokens_out = _estimate_tokens_for_groups(groups)
    # Resumen ejecutivo: entrada ~ todo lo generado arriba, 1 llamada más de salida.
    tokens_in += tokens_out
    tokens_out += MAX_OUTPUT_TOKENS
    return estimate_cost_usd(getattr(provider, "provider_name", "anthropic"), getattr(provider, "model", ""), tokens_in, tokens_out)


def estimate_combined_report_cost_usd(provider: AIProvider, payloads_by_section: dict[str, dict]) -> float:
    """Costo ESTIMADO del "reporte completo" — todas las secciones
    disponibles + 1 resumen ejecutivo global."""
    from src.reports.section_registry import SECTIONS, SECTIONS_ORDEN

    groups: list[tuple[str, dict, str]] = []
    for sid in SECTIONS_ORDEN:
        if sid not in payloads_by_section:
            continue
        spec = SECTIONS[sid]
        grupos_payload = payloads_by_section[sid].get("grupos", {})
        groups.extend((g.title, grupos_payload.get(g.id, {}), spec.business_context) for g in spec.groups)
    tokens_in, tokens_out = _estimate_tokens_for_groups(groups)
    tokens_in += tokens_out
    tokens_out += MAX_OUTPUT_TOKENS
    return estimate_cost_usd(getattr(provider, "provider_name", "anthropic"), getattr(provider, "model", ""), tokens_in, tokens_out)
