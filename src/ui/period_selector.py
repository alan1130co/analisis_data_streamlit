"""Selector de período (Año/Mes) reutilizable para gráficas con series
temporales.

Unifica el patrón que ya usaban por separado `closures_by_age.py`,
`closures_by_city.py`, `closures_by_country.py`, `closures_by_gender.py`,
`closures_by_process_type.py`, `closures_by_publication.py`,
`closures_by_sector.py` y `closures_by_state.py` (cada uno con su propia
copia casi idéntica de: diccionario de meses en español, cálculo de
etiqueta por defecto, `st.selectbox` de "Período") — un `st.selectbox`
poblado con los (año, mes) que tienen datos para esa gráfica específica,
con el mes activo del dashboard como selección inicial.

Solo importa Streamlit — NO importa pandas ni nada de `analytics/`. Recibe
la lista de períodos ya calculada (típicamente la salida de una función
`available_periods(df)` del módulo de analytics correspondiente) y
devuelve el (año, mes) elegido.
"""
from __future__ import annotations

import streamlit as st

MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def format_period_label(year: int, month: int) -> str:
    """'Julio 2026' — misma etiqueta que arma cada `st.selectbox` de período."""
    return f"{MONTHS_ES[month]} {year}"


def render_period_selector(
    periods: list[tuple[int, int]],
    default_year: int,
    default_month: int,
    key: str,
    label: str = "Período",
) -> tuple[int, int] | None:
    """Renderiza un `st.selectbox` con los períodos disponibles (más
    reciente primero, tal cual los devuelve `available_periods`) y
    devuelve el `(año, mes)` elegido.

    `default_year`/`default_month`: el mes activo del dashboard (el del
    selector global en `app.py`). Se usa como selección inicial si esta
    gráfica tiene datos para ese mes; si no, cae al período más reciente
    disponible (`periods[0]`) — igual criterio que tenía cada gráfica antes
    de unificarse acá.

    `key`: debe ser único por gráfica e incluir `default_year`/`default_month`
    (como ya hacía cada gráfica individualmente) para que Streamlit
    reinicialice el widget cuando cambia el mes global del dashboard, en vez
    de arrastrar una selección manual de un período anterior.

    Devuelve `None` si `periods` está vacío — el caller debe mostrar su
    propio `st.info` en ese caso (mismo mensaje que ya tenía cada gráfica,
    no se estandariza acá porque el texto varía según la sección).
    """
    if not periods:
        return None

    default = (default_year, default_month) if (default_year, default_month) in periods else periods[0]
    options_labels = [format_period_label(y, m) for (y, m) in periods]
    label_to_period = dict(zip(options_labels, periods))
    default_label = format_period_label(default[0], default[1])

    selected_label = st.selectbox(
        label,
        options=options_labels,
        index=options_labels.index(default_label),
        key=key,
    )
    return label_to_period[selected_label]
