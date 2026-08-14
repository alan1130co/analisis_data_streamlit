from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics.closures_by_publication import (
    closures_by_publication,
    closures_by_origen_pauta,
    available_periods,
)
from src.ui.period_selector import format_period_label, render_period_selector

_PALETTE_VIBRANTE = [
    "#2563EB",  # azul brillante
    "#EC4899",  # rosa magenta
    "#16A34A",  # verde
    "#F59E0B",  # amarillo/naranja
    "#8B5CF6",  # violeta
    "#06B6D4",  # cyan
    "#DC2626",  # rojo
    "#10B981",  # verde esmeralda
    "#F97316",  # naranja
    "#A855F7",  # violeta claro
    "#0EA5E9",  # azul cielo
    "#84CC16",  # lima
]


def render_closures_by_publication(
    df_clientify: pd.DataFrame,
    default_year: int,
    default_month: int,
) -> None:
    """Seccion que muestra cierres por video Y por origen de pauta."""

    st.markdown("### Cierres por video y origen de pauta")

    periods = available_periods(df_clientify)
    sel = render_period_selector(
        periods, default_year, default_month,
        key=f"closures_publi_period_{default_year}_{default_month}",
        label="Periodo",
    )
    if sel is None:
        st.info("No hay cierres registrados.")
        return
    sel_year, sel_month = sel
    selected_label = format_period_label(sel_year, sel_month)

    # === PARTE 1: Cierres por publicacion/video ===
    st.markdown("#### Que publicacion trajo mas cierres?")

    dist_publi = closures_by_publication(df_clientify, sel_year, sel_month)

    if dist_publi.empty:
        st.info(f"No hay cierres de redes/pauta en {selected_label}.")
    else:
        # Grafica: excluir "Sin publicacion marcada" del bar chart
        dist_grafica = dist_publi[dist_publi["Publicacion"] != "Sin publicacion marcada"]

        if not dist_grafica.empty:
            fig = px.bar(
                dist_grafica.head(15),
                x="Cierres",
                y="Publicacion",
                orientation="h",
                text="Cierres",
                color="Cierres",
                color_continuous_scale="Blues",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=max(360, 32 * len(dist_grafica.head(15))),
                margin=dict(l=20, r=80, t=20, b=20),
                yaxis=dict(autorange="reversed"),
                showlegend=False,
                xaxis_title="Cierres",
                yaxis_title="",
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### Detalle por publicacion")
        df_display = dist_publi.copy()
        df_display["Porcentaje"] = df_display["Porcentaje"].apply(lambda x: f"{x}%")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        total_pauta = int(dist_publi["Cierres"].sum())
        st.caption(
            f"Total {total_pauta} cierres de pauta/redes en {selected_label}. "
            f"Incluye Facebook, Instagram, WhatsApp, Messenger, Organico y Referido de Redes. "
            f"Los que aparecen como 'Sin publicacion marcada' son cierres de redes donde "
            f"no se especifico que publicacion los trajo."
        )

    st.markdown("---")

    # === PARTE 2: Cierres por origen de pauta ===
    st.markdown("#### Por que red social vinieron los cierres?")

    dist_origen = closures_by_origen_pauta(df_clientify, sel_year, sel_month)

    if dist_origen.empty:
        st.info(f"No hay cierres con origen de pauta marcado en {selected_label}.")
    else:
        fig2 = go.Figure(data=[go.Pie(
            labels=dist_origen["Origen"],
            values=dist_origen["Cierres"],
            hole=0.45,
            marker=dict(
                colors=_PALETTE_VIBRANTE[:len(dist_origen)],
                line=dict(color="white", width=2),
            ),
            textinfo="label+percent+value",
            hovertemplate="<b>%{label}</b><br>Cierres: %{value}<br>%{percent}<extra></extra>",
        )])
        total_origen = int(dist_origen["Cierres"].sum())
        fig2.update_layout(
            height=460,
            # Leyenda horizontal debajo (2026-08-14) en vez de columna
            # vertical fija a la derecha — mismo fix que el resto de las
            # donas de esta sección (`closures_by_sector.py`,
            # `closures_by_process_type.py`): r=140 fijo dejaba la dona
            # reducida en celulares angostos. Wrap automático a cualquier
            # ancho con orientation="h".
            margin=dict(l=20, r=20, t=20, b=90),
            showlegend=True,
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.12, font=dict(size=11)),
            annotations=[dict(
                text=f"<b>{total_origen}</b><br>Cierres",
                x=0.5, y=0.5, font_size=15, showarrow=False,
            )],
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            f"Total {total_origen} cierres de pauta en {selected_label}. "
            f"Categorias derivadas del Canal offline (no de 'Origen de la pauta' que viene sucio). "
            f"Los cierres con canal 'Organico' se agrupan en TikTok."
        )
