"""Sección: Eficiencia por asesor."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics.breakdowns import efficiency_by_advisor

_TRANSPARENT = "rgba(0,0,0,0)"
_PRIMARY = "#2563EB"

_X_COL = {
    "Marketing (pautas)": "% Efic. pauta",
    "Referidos": "% Efic. referidos",
}


def render_efficiency_by_advisor(
    df_period: pd.DataFrame,
    df_full: pd.DataFrame,
    team: str | None = None,
) -> None:
    st.subheader("🎯 Eficiencia por asesor")

    _team = team or "Marketing (pautas)"
    x_col = _X_COL.get(_team, "% Efic. global")

    data_chart = efficiency_by_advisor(df_period, df_full, team=_team, only_with_closures=True)
    data_table = efficiency_by_advisor(df_period, df_full, team=_team, only_with_closures=False)

    if data_table.empty:
        st.info("No hay asesores con leads en el período.")
        return

    col_chart, col_table = st.columns([3, 2])

    with col_chart:
        if not data_chart.empty and x_col in data_chart.columns:
            fig = px.bar(
                data_chart,
                y="Asesor",
                x=x_col,
                orientation="h",
                text=data_chart[x_col].apply(lambda v: f"{v:.1f}%"),
                color=x_col,
                color_continuous_scale=[[0.0, "#93C5FD"], [1.0, _PRIMARY]],
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=420,
                margin=dict(l=0, r=40, t=20, b=20),
                plot_bgcolor=_TRANSPARENT,
                paper_bgcolor=_TRANSPARENT,
                coloraxis_showscale=False,
                xaxis_title=x_col,
                yaxis_title=None,
                yaxis=dict(autorange="reversed"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay asesores con cierres en el período.")

    with col_table:
        fmt = {
            col: ("{:.1f}%" if col.startswith("%") else "{:,.0f}")
            for col in data_table.columns
            if col != "Asesor"
        }
        styled = data_table.style.format(fmt)
        st.dataframe(styled, use_container_width=True, hide_index=True)
