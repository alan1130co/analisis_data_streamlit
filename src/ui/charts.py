"""
Gráficos con Plotly para el dashboard.

TODO: implementar gráficos de:
- Evolución mensual de creados / cierres
- Embudo: Creados → Asignados → Calificados → Cierres
- Distribución de cierres por canal
- Ranking de comerciales
"""
import pandas as pd
import plotly.express as px
import streamlit as st


def render_funnel(metrics_dict: dict) -> None:
    """Renderiza el embudo de conversión."""
    data = pd.DataFrame({
        "Etapa": ["Creados", "Asignados", "Calificados", "Cierres"],
        "Cantidad": [
            metrics_dict["creados"],
            metrics_dict["asignados"],
            metrics_dict["calificados"],
            metrics_dict["total_cierres"],
        ],
    })
    fig = px.funnel(data, x="Cantidad", y="Etapa", color_discrete_sequence=["#2563EB"])
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300)
    st.plotly_chart(fig, use_container_width=True)
