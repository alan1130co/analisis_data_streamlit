"""Test UI para el selector de período NUEVO e independiente de la gráfica
"Cierres ... por mes de origen" (src/ui/sections/pauta_vs_referidos_antiguedad.py,
2026-09-04).

Usa `streamlit.testing.v1.AppTest` (mismo harness que
`tests/test_ad_spend_sections_ui.py`) porque `st.selectbox` necesita un
ScriptRunContext real. Compone `render_pauta_vs_referidos` (la dona, con su
propio selector) + `render_pauta_vs_referidos_antiguedad` (barras por
antigüedad + la gráfica nueva de mes de origen) en la misma app, igual que
hace `app.py`, para poder verificar que mover el selector NUEVO no afecta ni
la dona ni las barras de antigüedad de arriba — solo la gráfica de mes de
origen.
"""
import json

from streamlit.testing.v1 import AppTest


def _plotly_traces(app_test: AppTest, chart_index: int) -> list[dict]:
    chart = app_test.get("plotly_chart")[chart_index]
    spec = json.loads(chart.proto.spec)
    return spec["data"]


def _lead(canal_offline, creado, cierre, estado="activo", origen_pauta=None):
    return {
        "creado": creado, "propietario": "asesor", "estado": estado,
        "canal online": None, "Canal offline": canal_offline, "Origen de la pauta": origen_pauta,
        "Motivo de no cierre": "cliente potencial", "Cantidad de cierres": 1.0,
        "Fecha de cierre": cierre,
        "Fecha de segundo cierre": None, "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
    }


def _build_app():
    def app():
        import pandas as pd
        from tests.test_pauta_vs_referidos_antiguedad_ui import _lead
        from src.ui.sections.pauta_vs_referidos import render_pauta_vs_referidos
        from src.ui.sections.pauta_vs_referidos_antiguedad import render_pauta_vs_referidos_antiguedad

        df_full = pd.DataFrame([
            # Cierres "generales" de Agosto 2026 (alimentan la dona y las
            # barras de antigüedad, ambas ancladas al selector de ARRIBA).
            _lead("clientify - facebook", pd.Timestamp("2026-8-1"), pd.Timestamp("2026-8-5"), origen_pauta="facebook"),
            _lead("referido - amigo", pd.Timestamp("2026-8-2"), pd.Timestamp("2026-8-6")),
            # Clientify-Whatsapp / Formulario Facebook-CP con cierre en
            # AGOSTO 2026, mes de origen (creado) distinto cada uno.
            _lead("clientify - whatsapp", pd.Timestamp("2026-6-1"), pd.Timestamp("2026-8-10")),
            _lead("formulario de facebook - cliente potencial", pd.Timestamp("2026-7-1"), pd.Timestamp("2026-8-11")),
            # Mismo canal, pero con cierre en JULIO 2026 — solo debe aparecer
            # en la gráfica de mes de origen cuando el selector NUEVO
            # (independiente) se mueva a Julio, sin tocar la dona/antigüedad.
            _lead("clientify - whatsapp", pd.Timestamp("2026-7-1"), pd.Timestamp("2026-7-15")),
        ])

        sel = render_pauta_vs_referidos(df_full, 2026, 8)
        year, month = sel
        render_pauta_vs_referidos_antiguedad(df_full, year, month)

    return AppTest.from_function(app)


def test_selector_nuevo_es_independiente_y_default_es_el_mes_mas_reciente():
    at = _build_app()
    at.run()
    assert not at.exception

    # 2 selectboxes: [0] el de la dona "Pauta vs Referidos" (arriba),
    # [1] el nuevo, exclusivo de la gráfica de mes de origen.
    assert len(at.selectbox) == 2
    top_sb, wf_sb = at.selectbox[0], at.selectbox[1]

    # Ambos por defecto en Agosto 2026 (el mes más reciente con cierres).
    assert top_sb.value == "Agosto 2026"
    assert wf_sb.value == "Agosto 2026"
    assert set(wf_sb.options) == {"Agosto 2026", "Julio 2026"}


def test_mover_selector_nuevo_no_afecta_la_dona_ni_las_barras_de_antiguedad():
    at = _build_app()
    at.run()

    dona_antes = _plotly_traces(at, 0)
    barras_antiguedad_antes = _plotly_traces(at, 1)
    mes_origen_antes = _plotly_traces(at, 2)

    # La gráfica de mes de origen en Agosto: 2 meses de origen (2026-06, 2026-07).
    xs_antes = sorted(set(x for tr in mes_origen_antes for x in tr.get("x", [])))
    assert xs_antes == ["2026-06", "2026-07"]

    # Muevo SOLO el selector nuevo (índice 1) a Julio 2026.
    at.selectbox[1].select("Julio 2026").run()

    # El selector de arriba no cambió.
    assert at.selectbox[0].value == "Agosto 2026"

    # La dona y las barras de antigüedad (ancladas al selector de ARRIBA) no cambiaron.
    assert _plotly_traces(at, 0) == dona_antes
    assert _plotly_traces(at, 1) == barras_antiguedad_antes

    # Solo la gráfica de mes de origen cambió: ahora Julio 2026 (mes de
    # origen 2026-07 únicamente, el lead que cerró en julio).
    mes_origen_despues = _plotly_traces(at, 2)
    assert mes_origen_despues != mes_origen_antes
    xs_despues = sorted(set(x for tr in mes_origen_despues for x in tr.get("x", [])))
    assert xs_despues == ["2026-07"]

    total_despues = sum(sum(tr.get("y", [])) for tr in mes_origen_despues)
    assert total_despues == 1
