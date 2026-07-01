from __future__ import annotations
import pandas as pd
import streamlit as st

from src.analytics.closures_by_video import closures_by_video


def render_closures_by_video(
    df_clientify: pd.DataFrame,
    df_meta: pd.DataFrame | None,
    year: int,
    month: int,
) -> None:
    """Sección 'Cierres por video (Meta Ads)' del mes."""

    st.markdown("### 🎬 Cierres por video (Meta Ads)")

    if df_meta is None or df_meta.empty:
        st.info(
            "Cargá un CSV de Meta Ads desde el sidebar para ver qué videos "
            "trajeron más cierres este mes."
        )
        return

    df = closures_by_video(df_clientify, df_meta, year, month)

    if df.empty:
        st.info(f"No hay datos de Meta para {year}-{month:02d}.")
        return

    df_display = df.copy()
    df_display["Gasto USD"] = df_display["Gasto USD"].apply(lambda x: f"${x:,.2f}")
    df_display["Costo/cierre"] = df_display["Costo/cierre"].apply(
        lambda x: f"${x:,.2f}" if x and x > 0 else "—"
    )
    df_display["Cierres atribuidos"] = df_display["Cierres atribuidos"].apply(
        lambda x: f"{x:.1f}" if x and x > 0 else "0"
    )

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    total_cierres_estim = df["Cierres atribuidos"].sum()
    st.caption(
        f"📌 Cierres atribuidos según proporción de contactos generados por cada video. "
        f"Total estimado del mes: {total_cierres_estim:.1f} cierres pauta. "
        f"Para atribución exacta hace falta usar UTMs en Meta + capturarlos en Clientify."
    )
