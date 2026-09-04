"""Tests para los 2 selectores independientes (Año / Mes, ambos default
"Todos") en las 6 secciones de "Marketing e Inversión"
(src/ui/sections/ad_spend*.py).

Usa `streamlit.testing.v1.AppTest` (harness oficial de Streamlit) en vez de
llamar a las funciones `render_*` directamente — necesitan un ScriptRunContext
real para que `st.selectbox` funcione, y `AppTest` es la forma soportada de
correr un script de Streamlit "de mentira" y leer los widgets/elementos que
produce, incluyendo el spec JSON del gráfico Plotly renderizado (`el.proto.spec`).

Los 2 selectores y su lógica de combinación (`filter_by_anio_mes`) son
COMPARTIDOS por las 6 gráficas (`src/analytics/ad_spend.py`) — por eso las 4
combinaciones (Año=Todos/Mes=Todos, Año=X/Mes=Todos, Año=Todos/Mes=X,
Año=X/Mes=X) solo se testean exhaustivamente acá en 2 gráficas
representativas (`render_ad_spend`, la más simple, y `render_ad_spend_roas`,
la que tiene el caso especial de la línea de ROAS); las otras 4 solo
confirman el patrón (default "Todos"/"Todos" = tendencia completa, un filtro
puntual funciona) — no hace falta repetir las 4 combinaciones 6 veces cuando
el código de filtrado es uno solo.
"""
import json

from streamlit.testing.v1 import AppTest

from src.analytics.ad_spend import MESES_ES, TODOS


def _plotly_traces(app_test: AppTest) -> list[dict]:
    """Lista de traces (`spec["data"]`) del primer gráfico Plotly renderizado."""
    chart = app_test.get("plotly_chart")[0]
    spec = json.loads(chart.proto.spec)
    return spec["data"]


def _plotly_x_values(app_test: AppTest, trace_index: int = 0) -> list[str]:
    return list(_plotly_traces(app_test)[trace_index]["x"])


def _plotly_x_values_all_traces(app_test: AppTest) -> list[str]:
    """Concatena "x" de TODOS los traces — necesario para `render_ad_spend`,
    que usa `color="Mes_Año"` en `px.bar` y por lo tanto arma un trace
    separado POR MES (cada uno con una sola categoría en su "x"), a
    diferencia del resto de las 6 gráficas (un solo trace por métrica)."""
    xs: list[str] = []
    for trace in _plotly_traces(app_test):
        xs.extend(trace.get("x", []))
    return xs


class _FakeUploadedFile:
    """Mínimo doble de `st.file_uploader`'s `UploadedFile` — solo lo que
    `load_ad_spend_files`/`AdSpendLoader` necesitan: `.name` y `.getvalue()`."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def test_render_ad_spend_selector_anio_mes_4_combinaciones():
    def app():
        import streamlit as st
        from tests.test_ad_spend_sections_ui import _FakeUploadedFile
        from src.ui.sections.ad_spend import render_ad_spend

        csv = (
            b"Fecha,Divisa,Importe,Identificador de la transaccion\n"
            b"01/03/2025,USD,100,tx1\n"
            b"01/04/2025,USD,200,tx2\n"
            b"01/03/2026,USD,300,tx3\n"
        )
        render_ad_spend([_FakeUploadedFile("billing.csv", csv)])

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    anio_sb, mes_sb = at.selectbox[0], at.selectbox[1]
    assert anio_sb.options == [TODOS, "2025", "2026"]
    assert mes_sb.options == [TODOS] + list(MESES_ES.values())
    assert anio_sb.value == TODOS
    assert mes_sb.value == TODOS

    # 1. Año=Todos, Mes=Todos -> tendencia completa.
    assert _plotly_x_values_all_traces(at) == ["Marzo 2025", "Abril 2025", "Marzo 2026"]

    # 2. Año=2025, Mes=Todos -> todos los meses de 2025.
    at.selectbox[0].select("2025").run()
    assert _plotly_x_values_all_traces(at) == ["Marzo 2025", "Abril 2025"]

    # 3. Año=Todos, Mes=Marzo -> Marzo de todos los años (año contra año).
    at.selectbox[0].select(TODOS).run()
    at.selectbox[1].select("Marzo").run()
    assert _plotly_x_values_all_traces(at) == ["Marzo 2025", "Marzo 2026"]

    # 4. Año=2026, Mes=Marzo -> un único mes puntual.
    at.selectbox[0].select("2026").run()
    assert _plotly_x_values_all_traces(at) == ["Marzo 2026"]


def test_render_ad_spend_roas_selector_anio_mes_4_combinaciones_con_linea_roas_completa():
    def app():
        import streamlit as st
        import pandas as pd
        from src.ui.sections.ad_spend_roas import render_ad_spend_roas

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
            {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "300"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2025-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "300"},
            {"creado": pd.Timestamp("2025-04-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "400"},
            {"creado": pd.Timestamp("2026-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2026-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "500"},
        ])
        render_ad_spend_roas(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    anio_sb, mes_sb = at.selectbox[0], at.selectbox[1]
    assert anio_sb.options == [TODOS, "2025", "2026"]
    assert mes_sb.options == [TODOS] + list(MESES_ES.values())
    assert anio_sb.value == TODOS
    assert mes_sb.value == TODOS

    def bars_x():
        traces = _plotly_traces(at)
        return list(traces[0]["x"]), list(traces[1]["x"])

    def linea_roas_x():
        return list(_plotly_traces(at)[2]["x"])

    todos_los_meses = ["Marzo 2025", "Abril 2025", "Marzo 2026"]

    # 1. Año=Todos, Mes=Todos -> barras y línea muestran los 3 meses.
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == todos_los_meses
    assert linea_roas_x() == todos_los_meses

    # 2. Año=2025, Mes=Todos -> barras se reducen a 2025; línea sigue completa.
    at.selectbox[0].select("2025").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2025", "Abril 2025"]
    assert linea_roas_x() == todos_los_meses

    # 3. Año=Todos, Mes=Marzo -> barras: Marzo de ambos años; línea sigue completa.
    at.selectbox[0].select(TODOS).run()
    at.selectbox[1].select("Marzo").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2025", "Marzo 2026"]
    assert linea_roas_x() == todos_los_meses

    # 4. Año=2026 + Mes=Marzo -> barras: un único mes; línea sigue completa.
    at.selectbox[0].select("2026").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2026"]
    assert linea_roas_x() == todos_los_meses


def test_render_ad_spend_vs_closures_selector_anio_mes_default_y_filtro_puntual():
    def app():
        import streamlit as st
        import pandas as pd
        from src.ui.sections.ad_spend_vs_closures import render_ad_spend_vs_closures

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2026-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2026-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
        ])
        render_ad_spend_vs_closures(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    assert at.selectbox[0].options == [TODOS, "2026"]
    assert at.selectbox[0].value == TODOS
    assert at.selectbox[1].value == TODOS
    assert _plotly_x_values(at) == ["Marzo 2026", "Abril 2026"]

    at.selectbox[1].select("Marzo").run()
    assert _plotly_x_values(at) == ["Marzo 2026"]


def test_render_ad_spend_cost_per_lead_selector_anio_mes_default_y_filtro_puntual():
    def app():
        import streamlit as st
        import pandas as pd
        from src.ui.sections.ad_spend_cost_per_lead import render_ad_spend_cost_per_lead

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2026-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2026-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
        ])
        render_ad_spend_cost_per_lead(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    assert at.selectbox[0].options == [TODOS, "2026"]
    assert at.selectbox[0].value == TODOS
    assert at.selectbox[1].value == TODOS
    assert _plotly_x_values(at) == ["Marzo 2026", "Abril 2026"]

    at.selectbox[1].select("Marzo").run()
    assert _plotly_x_values(at) == ["Marzo 2026"]


def test_render_ad_spend_vs_revenue_selector_anio_mes_default_y_filtro_puntual():
    def app():
        import streamlit as st
        import pandas as pd
        from src.ui.sections.ad_spend_vs_revenue import render_ad_spend_vs_revenue

        # combine_ad_spend_and_revenue solo muestra desde enero 2025.
        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2025-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": "1000"},
        ])
        render_ad_spend_vs_revenue(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    assert at.selectbox[0].options == [TODOS, "2025"]
    assert at.selectbox[0].value == TODOS
    assert at.selectbox[1].value == TODOS
    assert set(_plotly_x_values(at)) == {"Marzo 2025", "Abril 2025"}

    at.selectbox[1].select("Marzo").run()
    assert set(_plotly_x_values(at)) == {"Marzo 2025"}


def test_render_ad_spend_total_roas_selector_anio_mes_default_y_linea_roas_completa():
    def app():
        import streamlit as st
        import pandas as pd
        from src.ui.sections.ad_spend_total_roas import render_ad_spend_total_roas

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2025-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "300"},
            {"creado": pd.Timestamp("2025-04-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "400"},
        ])
        render_ad_spend_total_roas(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    assert at.selectbox[0].value == TODOS
    assert at.selectbox[1].value == TODOS
    traces = _plotly_traces(at)
    assert list(traces[0]["x"]) == ["Marzo 2025", "Abril 2025"]
    assert list(traces[2]["x"]) == ["Marzo 2025", "Abril 2025"]

    at.selectbox[1].select("Marzo").run()
    traces = _plotly_traces(at)
    assert list(traces[0]["x"]) == ["Marzo 2025"]
    # Línea de ROAS: SIGUE trayendo ambos meses.
    assert list(traces[2]["x"]) == ["Marzo 2025", "Abril 2025"]
