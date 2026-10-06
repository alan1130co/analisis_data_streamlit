"""Sección: Gasto facturado por mes (cobros de Meta) — debajo de la gráfica
de gasto real/en pauta de `ad_spend.py`, para comparar ambos.

2 modos (ver `API_MODE`/`CSV_MODE`, decididos en `app.py` según la fuente
de gasto real elegida en `src/ui/meta_ads_source.py`):
  - `CSV_MODE`: reutiliza el mismo CSV de Facturación ya cargado arriba
    (sin pedirlo 2 veces) — comportamiento sin cambios desde que se agregó
    esta sección.
  - `API_MODE`: trae lo facturado automáticamente vía
    `src/data_sources/meta_billing_api.py` (`/act_{id}/activities`,
    cobros reales — ver ese módulo para los hallazgos empíricos completos),
    cacheado 15 minutos. El CSV queda como opción SECUNDARIA dentro de un
    expander, para contrastar sin ser requisito. Si la API falla por
    completo (sin token, error de red, etc.) cae al CSV del expander como
    única fuente, con un `st.warning` explicando qué pasó — nunca rompe la
    página.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.ad_spend import (
    TODOS,
    MESES_ES,
    anios_disponibles,
    combine_real_vs_billed_monthly,
    filter_by_anio_mes,
    monthly_ad_spend,
    monthly_ad_spend_with_period,
)
from src.config.settings import APP_TIMEZONE, META_ACCESS_TOKEN
from src.data_sources.meta_billing_api import DEFAULT_SINCE, MetaAdsAPIError, fetch_meta_billed_amount
from src.ui.sections.ad_spend import load_ad_spend_files
from src.utils.sync_timing import log_marker, timed_stage

API_MODE = "api"
CSV_MODE = "csv"

CACHE_TTL_SECONDS = 900

_COLOR_FACTURADO = "#F59E0B"


@st.cache_data(
    ttl=CACHE_TTL_SECONDS,
    show_spinner="Descargando lo facturado por Meta Ads (/activities, 3 cuentas en paralelo)...",
)
def _cached_fetch_meta_billed_amount(token: str, since: str, until: str) -> tuple[pd.DataFrame, list[str], str]:
    """Mismo patrón que `meta_ads_source._cached_fetch_meta_ad_spend`: el
    tercer valor (`fetched_at`) se calcula DENTRO de la función cacheada,
    así solo cambia en un cache MISS real."""
    log_marker("=== _cached_fetch_meta_billed_amount: INICIO (MISS) ===")
    with timed_stage("fetch_meta_billed_amount (3 cuentas en paralelo)"):
        df, warnings = fetch_meta_billed_amount(token=token, since=since, until=until)
    fetched_at = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    log_marker(f"=== _cached_fetch_meta_billed_amount: FIN (MISS) — {len(df)} cobro(s), {len(warnings)} advertencia(s) ===")
    return df, warnings, fetched_at


def clear_meta_billing_cache() -> None:
    """Limpia el cache de `_cached_fetch_meta_billed_amount` — el botón
    "Actualizar datos de Meta" (`src/ui/meta_ads_source.py`) llama a esta
    función JUNTO con `clear_meta_api_cache()`, para refrescar tanto el
    gasto real como lo facturado con un solo click."""
    _cached_fetch_meta_billed_amount.clear()


def _render_api_billed_block() -> tuple[pd.DataFrame, bool]:
    """Trae lo facturado por API (cacheado). Devuelve `(df, ok)` — `ok`
    es `False` si no hay token configurado o la llamada falló por completo
    (en ambos casos ya se mostró un `st.warning` explicando qué pasó, y el
    llamador debe caer al CSV del expander como única fuente)."""
    if not META_ACCESS_TOKEN:
        st.warning(
            "⚠️ Falta configurar `META_ACCESS_TOKEN` — no se puede traer lo "
            "facturado por API. Subí el CSV de facturación abajo para verlo igual."
        )
        return pd.DataFrame(), False

    until = pd.Timestamp.now(tz=APP_TIMEZONE).strftime("%Y-%m-%d")
    try:
        with timed_stage("_cached_fetch_meta_billed_amount (Gasto facturado, API)"):
            df, warnings, fetched_at = _cached_fetch_meta_billed_amount(META_ACCESS_TOKEN, DEFAULT_SINCE, until)
    except MetaAdsAPIError as exc:
        st.warning(
            f"⚠️ No se pudo traer lo facturado por la API de Meta: {exc}. "
            "Subí el CSV de facturación abajo para verlo igual."
        )
        return pd.DataFrame(), False

    for warning in warnings:
        st.warning(f"⚠️ {warning}")

    if not df.empty:
        fecha_min = df["Fecha"].min().strftime("%Y-%m-%d")
        fecha_max = df["Fecha"].max().strftime("%Y-%m-%d")
        st.caption(f"📅 Rango cubierto: {fecha_min} a {fecha_max}. Última actualización: {fetched_at}.")
    else:
        st.caption(f"Última actualización: {fetched_at}.")

    return df, True


def _render_csv_compare_expander(api_df: pd.DataFrame, api_ok: bool) -> pd.DataFrame:
    """Uploader SECUNDARIO/opcional, dentro de un expander, para contrastar
    contra el CSV de Facturación sin que sea requisito (ver `API_MODE`).
    Si la API funcionó Y también se subió un CSV, muestra una comparación
    rápida de totales (sin reemplazar la gráfica principal, que sigue
    usando los datos de la API)."""
    label = "📎 Comparar contra CSV de facturación" if api_ok else "📎 Subí el CSV de facturación (la API no respondió)"
    with st.expander(label, expanded=not api_ok):
        uploaded = st.file_uploader(
            "Subir CSV de facturación de Meta",
            type=["csv", "xls", "xlsx"],
            key="meta_billing_uploader_facturado",
            accept_multiple_files=True,
            help=(
                "Opcional — para contrastar contra lo que trae la API. Podés "
                "subir el histórico de 2025 y el de 2026 juntos: las filas "
                "repetidas entre ambos archivos se deduplican automáticamente."
            ),
        )
        csv_raw = load_ad_spend_files(uploaded)

        if api_ok and not api_df.empty and not csv_raw.empty:
            api_total = monthly_ad_spend(api_df)["Importe"].sum()
            csv_total = monthly_ad_spend(csv_raw)["Importe"].sum()
            st.caption(
                f"Total API: ${api_total:,.2f} — Total CSV: ${csv_total:,.2f} "
                f"(diferencia ${api_total - csv_total:,.2f})."
            )

    return csv_raw


def render_ad_spend_billed(
    mode: str,
    *,
    csv_reuse_raw: pd.DataFrame | None = None,
    real_raw: pd.DataFrame | None = None,
) -> None:
    """`mode`: `CSV_MODE` reutiliza `csv_reuse_raw` (CSV ya cargado arriba,
    sin pedirlo 2 veces); `API_MODE` trae lo facturado automáticamente por
    API, con el CSV como opción secundaria en un expander.
    `real_raw`: gasto real del mismo período (lo que muestra la gráfica de
    arriba) para la comparación opcional en el gráfico — `None` o vacío la
    omite sin error.

    2 selectores independientes: "Año" (`key="anio_ad_spend_billed"`) y
    "Mes" (`key="mes_ad_spend_billed"`), mismo patrón que el resto de
    "Marketing e Inversión" (ver `ad_spend.filter_by_anio_mes`).
    """
    st.markdown("### 🧾 Gasto facturado por mes (cobros de Meta)")

    if mode == CSV_MODE:
        billed_raw = csv_reuse_raw
    else:
        api_df, api_ok = _render_api_billed_block()
        csv_df = _render_csv_compare_expander(api_df, api_ok)
        billed_raw = api_df if api_ok and not api_df.empty else csv_df

    if billed_raw is None or billed_raw.empty:
        st.info(
            "Subí el CSV de facturación de Meta Ads para ver lo facturado "
            "(cobros) por mes."
        )
        return

    facturado_mensual = monthly_ad_spend_with_period(billed_raw)
    if facturado_mensual.empty:
        st.warning(
            "El archivo se cargó pero no se encontraron filas válidas en "
            "USD para calcular lo facturado."
        )
        return

    show_comparison = real_raw is not None and not real_raw.empty
    real_mensual = monthly_ad_spend_with_period(real_raw) if show_comparison else pd.DataFrame()
    comparativo = combine_real_vs_billed_monthly(real_mensual, facturado_mensual)

    meses_disponibles = list(facturado_mensual["Mes_Año"])
    c1, c2 = st.columns(2)
    anio_sel = c1.selectbox(
        "Año", options=[TODOS] + anios_disponibles(meses_disponibles),
        index=0, key="anio_ad_spend_billed",
    )
    mes_sel = c2.selectbox(
        "Mes", options=[TODOS] + list(MESES_ES.values()),
        index=0, key="mes_ad_spend_billed",
    )
    labels_permitidos = filter_by_anio_mes(meses_disponibles, anio_sel, mes_sel)
    facturado_mensual = facturado_mensual[facturado_mensual["Mes_Año"].isin(labels_permitidos)]
    comparativo = comparativo[comparativo["Mes_Año"].isin(labels_permitidos)]

    orden_meses = list(facturado_mensual["Mes_Año"])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=facturado_mensual["Mes_Año"],
        y=facturado_mensual["Importe"],
        name="Facturado (USD)",
        marker_color=_COLOR_FACTURADO,
        text=[f"${v:,.2f}" for v in facturado_mensual["Importe"]],
        textposition="outside",
    ))

    # Rango del eje Y con margen extra por encima de la barra más alta, para
    # que la etiqueta de valor nunca quede recortada arriba — mismo patrón
    # que el resto de "Marketing e Inversión".
    max_y = facturado_mensual["Importe"].max() if not facturado_mensual.empty else 0
    ymax = max_y * 1.25 if max_y > 0 else 1

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=orden_meses)
    fig.update_layout(
        template="plotly_white",
        xaxis=dict(title="Mes y año", tickangle=-45),
        yaxis=dict(title="Total facturado (USD)", tickprefix="$", tickformat=",.2f", range=[0, ymax]),
        showlegend=False,
        bargap=0.25,
        margin=dict(t=80),
    )
    fig.update_traces(cliponaxis=False)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Lo facturado difiere del gasto real porque Meta solo registra un "
        "cobro cuando el gasto acumulado llega a un umbral (~$900) — un "
        "gasto real ya hecho pero todavía no facturado no aparece acá."
    )

    if show_comparison and not comparativo.empty:
        with st.expander("Ver diferencia mensual (Real − Facturado)"):
            tabla = comparativo[["Mes_Año", "Importe_Real", "Importe_Facturado", "Diferencia"]].copy()
            for col in ["Importe_Real", "Importe_Facturado", "Diferencia"]:
                tabla[col] = tabla[col].apply(lambda v: f"${v:,.2f}")
            tabla.columns = ["Mes", "Gasto real", "Facturado", "Diferencia (Real − Facturado)"]
            st.dataframe(tabla, use_container_width=True, hide_index=True)
