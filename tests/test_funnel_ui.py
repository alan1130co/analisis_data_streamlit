"""Test UI para `src/ui/sections/funnel.py::render_funnel` — CAMBIO 2026-09-08:
César Augusto se excluye de la GRÁFICA de barras del embudo (su volumen de
Asignados aplasta visualmente al resto de los asesores), pero la TABLA de
abajo sigue mostrando su fila sin cambios.

Usa `streamlit.testing.v1.AppTest` (mismo harness que
`tests/test_pauta_vs_referidos_antiguedad_ui.py`) porque `st.selectbox`
necesita un ScriptRunContext real.
"""
import json

from streamlit.testing.v1 import AppTest


def _plotly_traces(app_test: AppTest, chart_index: int) -> list[dict]:
    chart = app_test.get("plotly_chart")[chart_index]
    spec = json.loads(chart.proto.spec)
    return spec["data"]


def _lead(propietario, creado, cierre=None, estado="activo"):
    return {
        "creado": creado, "propietario": propietario, "estado": estado,
        "canal online": None, "Canal offline": "clientify - whatsapp", "Origen de la pauta": None,
        "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0 if cierre else 0.0,
        "Fecha de cierre": cierre,
        "Fecha de segundo cierre": None, "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
    }


def _build_app():
    def app():
        import pandas as pd
        from tests.test_funnel_ui import _lead
        from src.ui.sections.funnel import render_funnel

        df_full = pd.DataFrame(
            # César Augusto: volumen grande que aplastaría la gráfica.
            [_lead("Cesar Augusto Perez Tafur", pd.Timestamp("2026-8-1")) for _ in range(50)]
            # Otro asesor, volumen normal.
            + [_lead("Ana Perdomo", pd.Timestamp("2026-8-2"), pd.Timestamp("2026-8-6"))]
        )
        render_funnel(df_full, 2026, 8)

    return AppTest.from_function(app)


def test_grafica_excluye_a_cesar_pero_tabla_lo_conserva():
    at = _build_app()
    at.run(timeout=15)
    assert not at.exception

    traces = _plotly_traces(at, 0)
    asesores_en_grafica = {x for tr in traces for x in tr.get("x", [])}
    assert "Cesar Augusto Perez Tafur".title() not in asesores_en_grafica
    assert "Ana Perdomo".title() in asesores_en_grafica

    tabla = at.dataframe[0].value
    asesores_en_tabla = set(tabla["Asesor"])
    assert "Cesar Augusto Perez Tafur".title() in asesores_en_tabla
    assert "Ana Perdomo".title() in asesores_en_tabla
