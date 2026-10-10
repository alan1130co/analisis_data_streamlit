"""Sección: Gasto en pauta publicitaria (Meta Ads)."""
from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    combine_ad_spend_sources,
    default_anio_index,
    filter_by_anio_mes,
    monthly_ad_spend,
)
from src.config.settings import APP_TIMEZONE
from src.data_sources.ad_spend_loader import AdSpendLoader


def _anio_actual() -> int:
    """Año actual en `APP_TIMEZONE` — usado como default del selector
    "Año". Función separada (no inline) para que los tests puedan
    neutralizarla con un sentinel que no exista en su fixture cuando lo que
    están probando es la mecánica de filtrado, no el default."""
    return pd.Timestamp.now(tz=APP_TIMEZONE).year


@st.cache_data(show_spinner=False)
def _load_ad_spend(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Lee y normaliza el reporte de Meta Ads UNA SOLA VEZ por archivo —
    mismo patrón de cache que `src/ui/upload.py` para el Excel principal, así
    no se relee el archivo en cada rerun de Streamlit."""
    loader = AdSpendLoader(io.BytesIO(file_bytes))
    loader._name = file_name
    return loader.load()


def load_ad_spend_files(uploaded_files) -> pd.DataFrame:
    """Carga y combina (concat + dedup) los archivos de Facturación de Meta
    Ads subidos. `uploaded_files` es la lista de `UploadedFile` crudos
    guardada en `st.session_state.meta_billing_files` (o None/[] si no se
    subió nada). Devuelve DataFrame vacío si no hay archivos o ninguno pudo
    leerse.

    Compartida entre `render_ad_spend` y `render_ad_spend_vs_closures`
    (`src/ui/sections/ad_spend_vs_closures.py`) para no reimplementar el
    mismo loop de carga en dos lugares — cada archivo individual ya está
    cacheado por `_load_ad_spend`, así que llamarla más de una vez por rerun
    de Streamlit no relee los archivos.
    """
    if not uploaded_files:
        return pd.DataFrame()

    frames = []
    for uploaded_file in uploaded_files:
        try:
            frames.append(_load_ad_spend(uploaded_file.getvalue(), uploaded_file.name))
        except Exception as e:
            st.error(f"Error leyendo '{uploaded_file.name}': {e}")

    return combine_ad_spend_sources(frames)


def render_ad_spend(uploaded_files) -> None:
    """Soporta cargar el histórico de facturación junto con reportes nuevos
    de distintas cuentas: cada archivo se lee y normaliza por separado, se
    concatenan y se deduplican por 'Identificador de la transacción' para no
    sumar dos veces un cobro si los rangos de fecha de los archivos se
    solapan (ver `load_ad_spend_files`).

    Fuente CSV únicamente — para la fuente API de Meta ver
    `render_ad_spend_from_raw`, que recibe el DataFrame ya cargado en vez de
    una lista de archivos subidos.
    """
    st.markdown("### 💰 Gasto en pauta publicitaria (Meta Ads)")

    if not uploaded_files:
        st.info(
            "Subí uno o más reportes de Facturación/Inversión de Meta Ads "
            "desde el panel lateral (histórico + reportes nuevos de cada "
            "cuenta) para ver la inversión en pauta publicitaria."
        )
        return

    raw = load_ad_spend_files(uploaded_files)
    if raw.empty:
        st.warning("No se pudo leer ningún archivo de facturación válido.")
        return

    _render_chart(raw)


def render_ad_spend_from_raw(raw: pd.DataFrame) -> None:
    """Misma gráfica que `render_ad_spend`, para la fuente API de Meta
    (gasto real diario ya agregado por `src/data_sources/meta_ads_api.py`)
    — recibe el DataFrame directo, sin pasar por `load_ad_spend_files`."""
    st.markdown("### 💰 Gasto en pauta publicitaria (Meta Ads)")

    if raw is None or raw.empty:
        st.info("No hay gasto registrado en la API de Meta para el rango consultado.")
        return

    _render_chart(raw)


@st.fragment
def _render_chart(raw: pd.DataFrame) -> None:
    """Cuerpo compartido por `render_ad_spend` (CSV) y
    `render_ad_spend_from_raw` (API). 2 selectores independientes: "Año"
    (`key="anio_ad_spend"`, default el año actual si está entre los datos —
    ver `default_anio_index` — si no "Todos") y "Mes" (`key="mes_ad_spend"`,
    default "Todos"). Año+Mes específicos combinan con AND (ver
    `ad_spend.filter_by_anio_mes`, compartida por las 6 gráficas de esta
    pestaña).

    Decorado con `@st.fragment`: cambiar cualquiera de los 2 selectores
    solo re-ejecuta ESTE bloque (filtrado + replot), no el resto de la
    pestaña "Marketing e Inversión" ni las cargas de datos de `render_ad_
    spend`/`render_ad_spend_from_raw` (que reciben `raw` ya cargado, fuera
    del fragment)."""
    data = monthly_ad_spend(raw)
    if data.empty:
        st.warning(
            "No se encontraron filas válidas en USD con columnas 'Fecha', "
            "'Divisa' e 'Importe'."
        )
        return

    data = data.copy()
    # "Mes_Año" ya viene en orden cronológico (ver monthly_ad_spend).
    meses_disponibles = list(data["Mes_Año"])
    anios = anios_disponibles(meses_disponibles)
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios,
        index=default_anio_index(anios, _anio_actual()), key="anio_ad_spend",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    data = data[data["Mes_Año"].isin(labels_permitidos)]

    orden_meses = list(data["Mes_Año"])

    # UN SOLO trace de barras con un color distinto por barra (vía
    # `marker_color`, una lista) — NO `px.bar(..., color="Mes_Año")` como
    # antes. Ese patrón crea un trace de Plotly POR MES (un color = un
    # trace, y acá "color" es la misma columna que "x"), y en `barmode`
    # "group"/"relative" (el default de Plotly) el ancho de cada barra se
    # divide entre el número TOTAL de traces de la figura, aunque cada
    # trace solo tenga datos en una categoría — con muchos meses (ver API de
    # Meta, que trae más historial que el CSV manual de antes) esto encogía
    # las barras a una fracción minúscula de su categoría, con mucho hueco
    # alrededor (bug reportado: barras "muy delgadas, con mucho espacio").
    # Mismo patrón de 1-trace-con-colores-por-barra que ya usan el resto de
    # gráficas de "Marketing e Inversión" (ver ad_spend_billed.py).
    paleta = px.colors.qualitative.Bold
    colores_por_barra = [paleta[i % len(paleta)] for i in range(len(data))]

    fig = go.Figure(go.Bar(
        x=data["Mes_Año"],
        y=data["Importe"],
        text=data["Importe"],
        texttemplate="$%{text:,.2f}",
        textposition="outside",
        textfont=dict(size=14),
        cliponaxis=False,
        marker_color=colores_por_barra,
    ))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden_meses)

    # Rango del eje Y con margen extra por encima de la barra más alta, para
    # que la etiqueta de valor ("$6,711.82") nunca quede recortada arriba —
    # mismo patrón ya usado en ad_spend_roas.py/ad_spend_total_roas.py.
    max_y = data["Importe"].max() if not data.empty else 0
    ymax = max_y * 1.25 if max_y > 0 else 1

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Mes y año",
        yaxis=dict(title="Total pagado (USD)", range=[0, ymax]),
        xaxis_tickangle=-45,
        showlegend=False,
        bargap=0.2,
        margin=dict(t=80),
    )
    st.plotly_chart(fig, use_container_width=True)
