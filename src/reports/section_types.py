"""Tipos compartidos de la arquitectura de reportes MULTI-SECCIÓN (una por
pestaña: Marketing e Inversión, Segmentación Clave, Embudo y Canales,
Gestión Comercial — ver `src/reports/section_registry.py`).

`ReportContext` es el único objeto que necesita conocer el orquestador/UI:
agrupa TODOS los insumos que cualquier grupo de cualquier sección podría
necesitar — cada `payload_builder`/`figures_builder` toma de ahí lo que le
sirve e ignora el resto, en vez de que cada sección tenga su propia firma
de argumentos distinta (lo que obligaría al orquestador a saber el detalle
de cada una).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd
from matplotlib.figure import Figure


@dataclass
class ReportContext:
    gasto_raw: pd.DataFrame
    billed_raw: pd.DataFrame | None
    df_clientify: pd.DataFrame
    year: int
    month: int
    team: str = "Todos"
    metrics: object | None = None
    metrics_prev: object | None = None
    anio_filter: int | str = "Todos"


PayloadBuilder = Callable[[ReportContext], dict]
FiguresBuilder = Callable[[ReportContext], dict[str, list[tuple[str, Figure]]]]
DataAvailable = Callable[[ReportContext], bool]


@dataclass
class GroupSpec:
    id: str
    title: str
    payload_builder: PayloadBuilder


@dataclass
class SectionSpec:
    id: str
    title: str
    groups: list[GroupSpec]
    figures_builder: FiguresBuilder
    data_available: DataAvailable
    no_data_message: str
    business_context: str

    @property
    def group_ids(self) -> list[str]:
        return [g.id for g in self.groups]

    @property
    def group_titles(self) -> dict[str, str]:
        return {g.id: g.title for g in self.groups}
