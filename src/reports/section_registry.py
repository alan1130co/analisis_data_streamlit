"""Registro central de las 4 secciones del reporte (una por pestaña de
`app.py`) — único lugar que conoce las 4 a la vez. El orquestador
(`report_orchestrator.py`) y la UI (`src/ui/report_generator.py`) solo
conocen `SECTIONS`/`SECTIONS_ORDEN`, nunca el detalle de cada módulo de
`analytics/report_payload*.py`/`reports/chart_builder_matplotlib*.py`.

Agregar una 5ta sección en el futuro = agregar su `SectionSpec` acá, nada
más — ni el orquestador ni la UI necesitan cambios.
"""
from __future__ import annotations

from src.analytics import report_payload as _marketing
from src.analytics import report_payload_embudo as _embudo
from src.analytics import report_payload_gestion_comercial as _gestion
from src.analytics import report_payload_segmentacion as _segmentacion
from src.config.report_prompts import (
    BUSINESS_CONTEXT_EMBUDO,
    BUSINESS_CONTEXT_GESTION_COMERCIAL,
    BUSINESS_CONTEXT_MARKETING,
    BUSINESS_CONTEXT_SEGMENTACION,
)
from src.reports import chart_builder_matplotlib as _marketing_figs
from src.reports import chart_builder_matplotlib_embudo as _embudo_figs
from src.reports import chart_builder_matplotlib_gestion_comercial as _gestion_figs
from src.reports import chart_builder_matplotlib_segmentacion as _segmentacion_figs
from src.reports.section_types import GroupSpec, SectionSpec

MARKETING = SectionSpec(
    id="marketing",
    title="Marketing e Inversión",
    groups=[
        GroupSpec(gid, _marketing.GRUPOS_TITULOS[gid], _marketing.group_payload_builder(gid))
        for gid in _marketing.GRUPOS_ORDEN
    ],
    figures_builder=lambda ctx: _marketing_figs.build_figures_by_group_mpl(
        ctx.gasto_raw, ctx.df_clientify, ctx.billed_raw, ctx.anio_filter
    ),
    data_available=lambda ctx: ctx.gasto_raw is not None and not ctx.gasto_raw.empty,
    no_data_message="No hay datos de gasto en pauta (Meta Ads) cargados — subí el CSV o conectá la API en el panel lateral.",
    business_context=BUSINESS_CONTEXT_MARKETING,
)

SEGMENTACION = SectionSpec(
    id="segmentacion",
    title="Segmentación Clave",
    groups=[
        GroupSpec(gid, _segmentacion.GRUPOS_TITULOS[gid], _segmentacion.group_payload_builder(gid))
        for gid in _segmentacion.GRUPOS_ORDEN
    ],
    figures_builder=lambda ctx: _segmentacion_figs.build_figures_by_group_mpl(
        ctx.df_clientify, ctx.year, ctx.month, ctx.team
    ),
    data_available=lambda ctx: ctx.df_clientify is not None and not ctx.df_clientify.empty,
    no_data_message="No hay datos de Clientify cargados — elegí una fuente de datos en el panel lateral.",
    business_context=BUSINESS_CONTEXT_SEGMENTACION,
)

EMBUDO = SectionSpec(
    id="embudo",
    title="Embudo y Canales",
    groups=[
        GroupSpec(gid, _embudo.GRUPOS_TITULOS[gid], _embudo.group_payload_builder(gid))
        for gid in _embudo.GRUPOS_ORDEN
    ],
    figures_builder=lambda ctx: _embudo_figs.build_figures_by_group_mpl(
        ctx.df_clientify, ctx.year, ctx.month, ctx.team
    ),
    data_available=lambda ctx: ctx.df_clientify is not None and not ctx.df_clientify.empty,
    no_data_message="No hay datos de Clientify cargados — elegí una fuente de datos en el panel lateral.",
    business_context=BUSINESS_CONTEXT_EMBUDO,
)

GESTION_COMERCIAL = SectionSpec(
    id="gestion_comercial",
    title="Gestión Comercial",
    groups=[
        GroupSpec(gid, _gestion.GRUPOS_TITULOS[gid], _gestion.group_payload_builder(gid))
        for gid in _gestion.GRUPOS_ORDEN
    ],
    figures_builder=lambda ctx: _gestion_figs.build_figures_by_group_mpl(
        ctx.df_clientify, ctx.year, ctx.month, ctx.metrics, ctx.metrics_prev
    ),
    data_available=lambda ctx: ctx.df_clientify is not None and not ctx.df_clientify.empty,
    no_data_message="No hay datos de Clientify cargados — elegí una fuente de datos en el panel lateral.",
    business_context=BUSINESS_CONTEXT_GESTION_COMERCIAL,
)

SECTIONS_ORDEN = ["marketing", "segmentacion", "embudo", "gestion_comercial"]

SECTIONS: dict[str, SectionSpec] = {
    "marketing": MARKETING,
    "segmentacion": SEGMENTACION,
    "embudo": EMBUDO,
    "gestion_comercial": GESTION_COMERCIAL,
}
