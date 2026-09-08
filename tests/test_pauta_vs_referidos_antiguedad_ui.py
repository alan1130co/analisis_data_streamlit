"""Test UI para el selector de período NUEVO e independiente de las gráficas
"Cierres ... por mes de origen" (src/ui/sections/pauta_vs_referidos_antiguedad.py,
2026-09-04; separadas en 2 gráficas por canal el 2026-09-08; convertidas de
barras a torta (pie) el 2026-09-08b).

Usa `streamlit.testing.v1.AppTest` (mismo harness que
`tests/test_ad_spend_sections_ui.py`) porque `st.selectbox` necesita un
ScriptRunContext real. Compone `render_pauta_vs_referidos` (la dona, con su
propio selector) + `render_pauta_vs_referidos_antiguedad` (tabla de detalle +
las 2 gráficas de mes de origen, una por canal) en la misma app, igual que
hace `app.py`, para poder verificar que mover el selector NUEVO no afecta la
dona de arriba — solo las gráficas de mes de origen.

2026-09-08: la gráfica de barras apiladas por antigüedad (cohortes) fue
eliminada de la sección (CAMBIO 3), así que ya no hay un chart_index fijo
para ella acá."""
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


def test_mover_selector_nuevo_no_afecta_la_dona():
    at = _build_app()
    at.run()

    dona_antes = _plotly_traces(at, 0)

    # Agosto: dona (0) + torta Clientify-Whatsapp (1) + torta Formulario
    # Facebook-CP (2) — cada canal tiene 1 cierre en Agosto, con mes de
    # origen distinto. Cada canal es un go.Pie (una porción por mes).
    assert len(at.get("plotly_chart")) == 3
    whatsapp_antes = _plotly_traces(at, 1)
    facebook_cp_antes = _plotly_traces(at, 2)
    assert whatsapp_antes[0]["type"] == "pie"
    assert facebook_cp_antes[0]["type"] == "pie"

    labels_whatsapp_antes = sorted(set(l for tr in whatsapp_antes for l in tr.get("labels", [])))
    labels_facebook_cp_antes = sorted(set(l for tr in facebook_cp_antes for l in tr.get("labels", [])))
    assert labels_whatsapp_antes == ["Jun 2026"]
    assert labels_facebook_cp_antes == ["Jul 2026"]

    # Etiqueta de la porción = "<mes>: <cantidad>".
    assert whatsapp_antes[0]["text"] == ["Jun 2026: 1"]
    assert facebook_cp_antes[0]["text"] == ["Jul 2026: 1"]

    # Muevo SOLO el selector nuevo (índice 1) a Julio 2026.
    at.selectbox[1].select("Julio 2026").run()

    # El selector de arriba y la dona (anclada a él) no cambiaron.
    assert at.selectbox[0].value == "Agosto 2026"
    assert _plotly_traces(at, 0) == dona_antes

    # En Julio solo hay 1 cierre de Clientify-Whatsapp (mes de origen
    # 2026-07); Formulario Facebook-CP no tiene cierres en julio, así que
    # esa torta ni se dibuja (queda dona + 1 sola torta de canal).
    assert len(at.get("plotly_chart")) == 2
    whatsapp_despues = _plotly_traces(at, 1)
    labels_whatsapp_despues = sorted(set(l for tr in whatsapp_despues for l in tr.get("labels", [])))
    assert labels_whatsapp_despues == ["Jul 2026"]

    total_whatsapp_despues = sum(sum(tr.get("values", [])) for tr in whatsapp_despues)
    assert total_whatsapp_despues == 1
