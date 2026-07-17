"""Sección histórica: distribución de motivos de no cierre por mes/año/asesor."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.no_closure import available_advisors_in_period, motive_distribution_filtered
from src.config.settings import FOUNDING_DATE

_PALETTE = [
    "#2563EB", "#16A34A", "#7C3AED", "#EA580C", "#0891B2",
    "#DC2626", "#D97706", "#059669", "#9333EA", "#E11D48",
    "#94A3B8", "#0EA5E9", "#10B981", "#F59E0B", "#A855F7",
]

_MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def render_no_closure_history(
    df_unfiltered: pd.DataFrame,
    default_year: int,
    default_month: int,
) -> None:
    """Distribución de motivos de no cierre filtrable por año, mes y asesor."""
    st.markdown("### 📅 Motivos de no cierre — histórico por asesor")

    creado = pd.to_datetime(df_unfiltered["creado"], errors="coerce")
    years_avail = sorted(
        [y for y in creado.dt.year.dropna().unique() if y >= FOUNDING_DATE[0]],
        reverse=True,
    )

    if not years_avail:
        st.info("No hay datos para mostrar.")
        return

    col_y, col_m, col_a = st.columns([1, 1, 2])

    with col_y:
        year = st.selectbox(
            "Año",
            options=years_avail,
            index=years_avail.index(default_year) if default_year in years_avail else 0,
            key=f"ncl_history_year_{default_year}_{default_month}",
        )

    with col_m:
        month_label_to_num = {v: k for k, v in _MONTHS_ES.items()}
        month_options = list(_MONTHS_ES.values())
        default_label = _MONTHS_ES.get(default_month, "Enero")
        month_label = st.selectbox(
            "Mes",
            options=month_options,
            index=month_options.index(default_label),
            key=f"ncl_history_month_{default_year}_{default_month}",
        )
        month = month_label_to_num[month_label]

    with col_a:
        advisors = available_advisors_in_period(df_unfiltered, year, month)
        advisor = st.selectbox(
            "Asesor",
            options=["Todos"] + advisors,
            index=0,
            key=f"ncl_history_advisor_{year}_{month}",
        )

    dist = motive_distribution_filtered(df_unfiltered, year, month, advisor)

    if dist.empty:
        adv_text = f" del asesor {advisor}" if advisor != "Todos" else ""
        st.info(f"No hay leads para {month_label} {year}{adv_text}.")
        return

    total = int(dist["Cantidad"].sum())
    n = len(dist)

    fig = go.Figure(data=[go.Pie(
        labels=dist["Motivo"],
        values=dist["Cantidad"],
        hole=0.45,
        sort=False,
        pull=[0.02] * n,
        marker=dict(
            colors=_PALETTE[:n],
            line=dict(color="white", width=2),
        ),
        textposition="auto",
        textinfo="label+percent+value",
        textfont=dict(size=10),
        hovertemplate="<b>%{label}</b><br>Cantidad: %{value}<br>%{percent}<extra></extra>",
    )])
    fig.update_layout(
        height=560,
        margin=dict(l=120, r=200, t=40, b=60),
        showlegend=True,
        legend=dict(font=dict(size=10), orientation="v", x=1.05, y=0.5),
        uniformtext_minsize=9,
        uniformtext_mode="hide",
        annotations=[dict(
            text=f"<b>{total}</b><br>Leads",
            x=0.5, y=0.5,
            font_size=15,
            showarrow=False,
        )],
    )
    st.plotly_chart(fig, use_container_width=True)

    adv_text = advisor if advisor != "Todos" else "todos los asesores"
    st.caption(f"Mostrando {total} leads creados en {month_label} {year} para {adv_text}.")
