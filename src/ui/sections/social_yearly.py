"""Sección: Redes sociales — Leads y cierres año a la fecha."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.social_yearly import social_yearly

_TRANSPARENT = "rgba(0,0,0,0)"


def render_social_yearly(df_unfiltered: pd.DataFrame, current_year: int) -> None:
    st.subheader("📱 Redes sociales — Leads y cierres año a la fecha")

    parsed = pd.to_datetime(df_unfiltered.get("creado", pd.Series(dtype="object")), errors="coerce")
    years = sorted(parsed.dt.year.dropna().unique().astype(int).tolist())
    if not years:
        st.info("No hay datos disponibles.")
        return

    year_idx = years.index(current_year) if current_year in years else len(years) - 1
    year_sel = st.selectbox("Año", years, index=year_idx, key="social_yearly_year")

    data = social_yearly(df_unfiltered, year_sel)
    data_filtered = data[(data["Leads_redes"] > 0) | (data["Cierres_redes"] > 0)]

    if data_filtered.empty:
        st.info("No hay datos de redes sociales para este año.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Leads redes",
        x=data_filtered["mes"],
        y=data_filtered["Leads_redes"],
        marker_color="#7C3AED",
        text=data_filtered["Leads_redes"],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Cierres redes",
        x=data_filtered["mes"],
        y=data_filtered["Cierres_redes"],
        marker_color="#0891B2",
        text=data_filtered["Cierres_redes"],
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        height=380,
        margin=dict(l=0, r=20, t=30, b=20),
        plot_bgcolor=_TRANSPARENT,
        paper_bgcolor=_TRANSPARENT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
