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


def _plotly_xaxis_range(app_test: AppTest) -> list[float] | None:
    chart = app_test.get("plotly_chart")[0]
    spec = json.loads(chart.proto.spec)
    return spec["layout"]["xaxis"].get("range")


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


def test_render_ad_spend_selector_anio_mes_4_combinaciones(monkeypatch):
    # Este test es sobre la MECÁNICA de filtrado Año/Mes (no sobre el
    # default = año actual, cubierto en tests/test_ad_spend.py y en
    # test_ad_spend_billed_año_actual_ui.py) — se neutraliza el año actual a
    # un sentinel ausente del fixture (vía `monkeypatch`, auto-revierte al
    # terminar el test — una asignación directa dejaría el módulo real
    # mutado para el resto de la sesión de pytest) para que el default siga
    # siendo "Todos", como asumen las 4 combinaciones de este test.
    from src.ui.sections import ad_spend as ad_spend_section
    monkeypatch.setattr(ad_spend_section, "_anio_actual", lambda: 1900)

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


def test_render_ad_spend_roas_selector_anio_mes_4_combinaciones_con_linea_roas_completa(monkeypatch):
    # Neutraliza el default = año actual (ver test arriba) — este test es
    # sobre la mecánica de filtrado, no sobre el default.
    from src.ui.sections import ad_spend_roas as ad_spend_roas_section
    monkeypatch.setattr(ad_spend_roas_section, "_anio_actual", lambda: 1900)

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

    # 1. Año=Todos, Mes=Todos -> barras y línea muestran los 3 meses
    #    (histórico completo, comportamiento confirmado, sin cambios).
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == todos_los_meses
    assert linea_roas_x() == todos_los_meses

    # 2. Año=2025, Mes=Todos -> barras Y línea se reducen a los meses de 2025
    #    (fix 2026-10-05: antes la línea seguía trayendo "Marzo 2026" aunque
    #    el usuario hubiera elegido Año=2025 — bug reportado por el usuario).
    at.selectbox[0].select("2025").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2025", "Abril 2025"]
    assert linea_roas_x() == ["Marzo 2025", "Abril 2025"]

    # 3. Año=Todos, Mes=Marzo -> barras: Marzo de ambos años; línea sigue
    #    completa (el filtro de Mes nunca restringe la línea, solo el Año).
    at.selectbox[0].select(TODOS).run()
    at.selectbox[1].select("Marzo").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2025", "Marzo 2026"]
    assert linea_roas_x() == todos_los_meses

    # 4. Año=2026 + Mes=Marzo -> barras: un único mes; línea recortada a los
    #    meses de 2026 (acá solo hay uno en el fixture).
    at.selectbox[0].select("2026").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2026"]
    assert linea_roas_x() == ["Marzo 2026"]


def test_render_ad_spend_roas_anio_especifico_no_filtra_otros_anios_de_la_linea_roas():
    """Regresión del bug reportado: elegir Año=2025 no debe dejar ver meses
    de 2026 (ni de ningún otro año) en la línea de ROAS ni en el eje X,
    aunque el selector de Mes siga en "Todos"."""
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_roas import render_ad_spend_roas

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/01/2026", "Divisa": "USD", "Importe": "150"},
            {"Fecha": "01/10/2026", "Divisa": "USD", "Importe": "300"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2025-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "300"},
        ])
        render_ad_spend_roas(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    at.selectbox[0].select("2025").run()
    traces = _plotly_traces(at)
    linea_roas_x = list(traces[2]["x"])
    assert linea_roas_x == ["Marzo 2025"]
    assert "Enero 2026" not in linea_roas_x
    assert "Octubre 2026" not in linea_roas_x


def test_render_ad_spend_roas_eje_x_compacto_solo_cuando_anio_y_mes_son_especificos():
    """Cambio 2026-09-21: el `categoryarray` sigue completo siempre (para no
    desordenar la línea de ROAS, ver test de arriba), pero cuando Año Y Mes
    son ambos específicos se aplica un "zoom" (`xaxis.range`) para que la
    vista quede compacta en esa única barra. Con Año=Todos o Mes=Todos no se
    aplica ningún rango — eje completo, comportamiento actual."""
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

    # 1. Año=Todos, Mes=Todos -> sin rango (eje completo).
    assert _plotly_xaxis_range(at) is None

    # 2. Año=2025, Mes=Todos -> sin rango (solo Año no activa el zoom).
    at.selectbox[0].select("2025").run()
    assert _plotly_xaxis_range(at) is None

    # 3. Año=Todos, Mes=Marzo -> sin rango (solo Mes no activa el zoom).
    at.selectbox[0].select(TODOS).run()
    at.selectbox[1].select("Marzo").run()
    assert _plotly_xaxis_range(at) is None

    # 4. Año=2026 + Mes=Marzo -> rango de zoom sobre "Marzo 2026" (índice 0
    # dentro del categoryarray recortado a los meses de 2026, ["Marzo 2026"]
    # — ya no el categoryarray completo de los 3 meses, ver fix 2026-10-05).
    at.selectbox[0].select("2026").run()
    assert _plotly_xaxis_range(at) == [-0.5, 0.5]


def test_render_ad_spend_total_roas_eje_x_compacto_solo_cuando_anio_y_mes_son_especificos():
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

    assert _plotly_xaxis_range(at) is None

    at.selectbox[1].select("Marzo").run()
    assert _plotly_xaxis_range(at) is None  # solo Mes -> sin rango

    at.selectbox[0].select("2025").run()
    assert _plotly_xaxis_range(at) == [-0.5, 0.5]  # "Marzo 2025" es índice 0


def test_render_ad_spend_total_roas_anio_especifico_no_filtra_otros_anios_de_la_linea_roas():
    """Mismo patrón de selector Año/Mes que `ad_spend_roas.py` — misma
    regresión: elegir un Año puntual no debe dejar ver meses de otros años
    en la línea de ROAS ni en el eje X."""
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_total_roas import render_ad_spend_total_roas

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/01/2026", "Divisa": "USD", "Importe": "150"},
            {"Fecha": "01/10/2026", "Divisa": "USD", "Importe": "300"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2025-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "300"},
        ])
        render_ad_spend_total_roas(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    at.selectbox[0].select("2025").run()
    traces = _plotly_traces(at)
    linea_roas_x = list(traces[2]["x"])
    assert linea_roas_x == ["Marzo 2025"]
    assert "Enero 2026" not in linea_roas_x
    assert "Octubre 2026" not in linea_roas_x


def test_render_ad_spend_vs_closures_selector_anio_mes_default_y_filtro_puntual(monkeypatch):
    # Neutraliza el default = año actual (ver primer test del archivo) —
    # este test es sobre la mecánica de filtrado, no sobre el default.
    from src.ui.sections import ad_spend_vs_closures as ad_spend_vs_closures_section
    monkeypatch.setattr(ad_spend_vs_closures_section, "_anio_actual", lambda: 1900)

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


def test_render_ad_spend_cost_per_lead_selector_anio_mes_default_y_filtro_puntual(monkeypatch):
    # Neutraliza el default = año actual (ver primer test del archivo) —
    # este test es sobre la mecánica de filtrado, no sobre el default.
    from src.ui.sections import ad_spend_cost_per_lead as ad_spend_cost_per_lead_section
    monkeypatch.setattr(ad_spend_cost_per_lead_section, "_anio_actual", lambda: 1900)

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


def test_render_ad_spend_vs_process_value_selector_anio_mes_default_y_filtro_puntual(monkeypatch):
    # Neutraliza el default = año actual (ver primer test del archivo) —
    # este test es sobre la mecánica de filtrado, no sobre el default.
    from src.ui.sections import ad_spend_vs_process_value as ad_spend_vs_process_value_section
    monkeypatch.setattr(ad_spend_vs_process_value_section, "_anio_actual", lambda: 1900)

    def app():
        import streamlit as st
        import pandas as pd
        from src.ui.sections.ad_spend_vs_process_value import render_ad_spend_vs_process_value

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp("2026-03-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2026-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": "5000"},
            {"creado": pd.Timestamp("2026-04-01"), "estado": "activo",
             "Canal offline": "referido puro", "Origen de la pauta": None,
             "canal online": None,
             "Fecha de cierre": pd.Timestamp("2026-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": "9000"},  # Referido puro: NO debe sumar acá.
        ])
        render_ad_spend_vs_process_value(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    assert at.selectbox[0].options == [TODOS, "2026"]
    assert at.selectbox[0].value == TODOS
    assert at.selectbox[1].value == TODOS

    traces = _plotly_traces(at)
    assert list(traces[0]["x"]) == ["Marzo 2026", "Abril 2026"]

    at.selectbox[1].select("Marzo").run()
    traces = _plotly_traces(at)
    assert list(traces[0]["x"]) == ["Marzo 2026"]


def _df_clientify_process_value_roas_fixture():
    import pandas as pd

    return pd.DataFrame([
        {"creado": pd.Timestamp("2025-03-01"), "estado": "activo",
         "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
         "canal online": "paid social",
         "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
         "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
         "Valor total del proceso": "3000"},
        {"creado": pd.Timestamp("2025-04-01"), "estado": "activo",
         "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
         "canal online": "paid social",
         "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
         "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
         "Valor total del proceso": "4000"},
        {"creado": pd.Timestamp("2026-03-01"), "estado": "activo",
         "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
         "canal online": "paid social",
         "Fecha de cierre": pd.Timestamp("2026-03-05"), "Fecha de segundo cierre": None,
         "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
         "Valor total del proceso": "5000"},
        {"creado": pd.Timestamp("2025-05-01"), "estado": "activo",
         "Canal offline": "referido puro", "Origen de la pauta": None,
         "canal online": None,
         "Fecha de cierre": pd.Timestamp("2025-05-05"), "Fecha de segundo cierre": None,
         "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
         "Valor total del proceso": "9999"},  # Referido puro: NO debe sumar.
    ])


def test_render_ad_spend_vs_process_value_roas_selector_anio_mes_4_combinaciones_con_linea_roas(monkeypatch):
    # Neutraliza el default = año actual (ver primer test del archivo) —
    # este test es sobre la mecánica de filtrado, no sobre el default.
    from src.ui.sections import ad_spend_vs_process_value_roas as ad_spend_vs_process_value_roas_section
    monkeypatch.setattr(ad_spend_vs_process_value_roas_section, "_anio_actual", lambda: 1900)

    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_process_value_roas import render_ad_spend_vs_process_value_roas
        from tests.test_ad_spend_sections_ui import _df_clientify_process_value_roas_fixture

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
            {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "300"},
        ])
        render_ad_spend_vs_process_value_roas(gasto_raw, _df_clientify_process_value_roas_fixture())

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

    # 2. Año=2025, Mes=Todos -> barras Y línea se recortan a 2025 (sin dejar
    # ver "Marzo 2026" — ver fix del bug de los selectores de ROAS).
    at.selectbox[0].select("2025").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2025", "Abril 2025"]
    assert linea_roas_x() == ["Marzo 2025", "Abril 2025"]

    # 3. Año=Todos, Mes=Marzo -> barras: Marzo de ambos años; línea completa.
    at.selectbox[0].select(TODOS).run()
    at.selectbox[1].select("Marzo").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2025", "Marzo 2026"]
    assert linea_roas_x() == todos_los_meses

    # 4. Año=2026 + Mes=Marzo -> barras: un único mes; línea recortada a 2026.
    at.selectbox[0].select("2026").run()
    gasto_x, ing_x = bars_x()
    assert gasto_x == ing_x == ["Marzo 2026"]
    assert linea_roas_x() == ["Marzo 2026"]


def test_render_ad_spend_vs_process_value_roas_usa_valor_total_del_proceso_de_cierres_de_pauta():
    """El ingreso debe tener el MISMO alcance que "Gasto en pauta vs Valor
    Total del Proceso (cierres de redes)": solo cierres de Pauta, el
    "Referido puro" queda excluido (lo verifica el valor de la barra de
    ingreso de Marzo 2025: 3000, NO 3000+9999)."""
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_process_value_roas import render_ad_spend_vs_process_value_roas
        from tests.test_ad_spend_sections_ui import _df_clientify_process_value_roas_fixture

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
        ])
        render_ad_spend_vs_process_value_roas(gasto_raw, _df_clientify_process_value_roas_fixture())

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    at.selectbox[1].select("Marzo").run()
    at.selectbox[0].select("2025").run()
    traces = _plotly_traces(at)
    # Los valores numéricos vienen serializados en binario (dtype/bdata) en
    # las versiones recientes de Plotly — se comparan vía el texto de la
    # etiqueta (siempre una lista plana de strings) en vez de "y".
    assert list(traces[1]["text"]) == ["$3,000"]
    # Línea de ROAS: recortada a los meses de 2025 (Marzo + Abril, ver fix
    # del bug de los selectores) — en Marzo 2025, ROAS = 3000 / 100 = 30x.
    roas_x = list(traces[2]["x"])
    roas_text = list(traces[2]["text"])
    assert roas_text[roas_x.index("Marzo 2025")] == "30.00x"


def test_render_ad_spend_vs_process_value_roas_yaxis_range_deja_margen_para_etiquetas():
    """Mismo patrón de margen de eje Y que `ad_spend_roas.py` (task 2: las
    etiquetas de valor no deben recortarse cuando la barra es alta)."""
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_process_value_roas import render_ad_spend_vs_process_value_roas
        from tests.test_ad_spend_sections_ui import _df_clientify_process_value_roas_fixture

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
        ])
        render_ad_spend_vs_process_value_roas(gasto_raw, _df_clientify_process_value_roas_fixture())

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    # Acota a un único mes (Marzo 2025) para que el máximo de las barras sea
    # determinístico: Importe=100, Valor_Proceso_Pauta=3000.
    at.selectbox[1].select("Marzo").run()
    at.selectbox[0].select("2025").run()

    chart = at.get("plotly_chart")[0]
    spec = json.loads(chart.proto.spec)
    y_range = spec["layout"]["yaxis"]["range"]
    max_bar_value = 3000.0
    assert y_range[1] > max_bar_value
    assert y_range[1] == max_bar_value * 1.25
    for trace in spec["data"]:
        if trace.get("type") == "bar":
            assert trace.get("cliponaxis") is False


def test_bar_charts_yaxis_range_deja_margen_para_que_el_valor_no_se_recorte():
    """Task 2: en barras muy altas, la etiqueta de valor ("$6,711.82") no
    debe recortarse arriba — todas las gráficas de barras de "Marketing e
    Inversión" deben reservar margen extra en el eje Y por encima del valor
    máximo (y no recortar el texto con `cliponaxis`)."""
    casos = []

    def app_ad_spend():
        from src.ui.sections.ad_spend import render_ad_spend
        from tests.test_ad_spend_sections_ui import _FakeUploadedFile
        csv = b"Fecha,Divisa,Importe\n01/03/2025,USD,6711.82\n"
        render_ad_spend([_FakeUploadedFile("billing.csv", csv)])

    casos.append(("ad_spend", app_ad_spend, 6711.82))

    def app_vs_revenue():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_revenue import render_ad_spend_vs_revenue
        gasto_raw = pd.DataFrame([{"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"}])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": "6711.82"},
        ])
        render_ad_spend_vs_revenue(gasto_raw, df_clientify)

    casos.append(("ad_spend_vs_revenue", app_vs_revenue, 6711.82))

    def app_cost_per_lead():
        import pandas as pd
        from src.ui.sections.ad_spend_cost_per_lead import render_ad_spend_cost_per_lead
        gasto_raw = pd.DataFrame([{"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "6711.82"}])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
        ])
        render_ad_spend_cost_per_lead(gasto_raw, df_clientify)

    casos.append(("ad_spend_cost_per_lead", app_cost_per_lead, 6711.82))

    def app_vs_closures():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_closures import render_ad_spend_vs_closures
        gasto_raw = pd.DataFrame([{"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "6711.82"}])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
        ])
        render_ad_spend_vs_closures(gasto_raw, df_clientify)

    casos.append(("ad_spend_vs_closures", app_vs_closures, 6711.82))

    def app_vs_process_value():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_process_value import render_ad_spend_vs_process_value
        gasto_raw = pd.DataFrame([{"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"}])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": "6711.82"},
        ])
        render_ad_spend_vs_process_value(gasto_raw, df_clientify)

    casos.append(("ad_spend_vs_process_value", app_vs_process_value, 6711.82))

    for nombre, app_fn, max_value in casos:
        at = AppTest.from_function(app_fn)
        at.run()
        assert not at.exception, f"{nombre}: {at.exception}"

        chart = at.get("plotly_chart")[0]
        spec = json.loads(chart.proto.spec)
        bar_traces = [t for t in spec["data"] if t.get("type") == "bar"]
        assert bar_traces, f"{nombre}: no se encontraron trazas de barras"
        for trace in bar_traces:
            assert trace.get("cliponaxis") is False, f"{nombre}: cliponaxis debe ser False"

        # yaxis primario (el que trae las barras) debe tener rango con
        # margen por encima del valor máximo graficado.
        yaxis = spec["layout"]["yaxis"]
        assert "range" in yaxis, f"{nombre}: falta 'range' en el eje Y"
        assert yaxis["range"][1] > max_value, f"{nombre}: el rango no deja margen sobre el valor máximo"


def test_render_ad_spend_cost_per_lead_barra_y_linea_quedan_en_paneles_separados():
    """Regresión del bug reportado (2026-10-07): en "Gasto en pauta vs.
    Costo promedio por lead de redes", cuando el punto de la línea caía a
    una altura de píxel similar a la de la barra de ese mismo mes, las 2
    etiquetas de texto quedaban encimadas e ilegibles (ej. "$7,656.03"
    sobre "$390.67"). Fix: barra y línea ahora viven en 2 PANELES
    APILADOS con eje Y propio cada uno — no pueden colisionar en altura de
    píxel sin importar qué tan parecidas sean sus fracciones normalizadas
    (antes el caso de colisión real: Importe=800 ambos meses, Valor_por_Lead
    Marzo=800/2=400 con fracción casi idéntica a la de la barra)."""
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_cost_per_lead import render_ad_spend_cost_per_lead

        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "800"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "800"},
        ])

        filas = []
        for _ in range(2):  # Marzo: 2 cierres -> Valor_por_Lead = 800/2 = 400
            filas.append({
                "estado": "activo", "Canal offline": "Clientify - Facebook",
                "Origen de la pauta": "Facebook", "canal online": "paid social",
                "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
                "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
            })
        for _ in range(16):  # Abril: 16 cierres -> Valor_por_Lead = 800/16 = 50
            filas.append({
                "estado": "activo", "Canal offline": "Clientify - Facebook",
                "Origen de la pauta": "Facebook", "canal online": "paid social",
                "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
                "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
            })
        df_clientify = pd.DataFrame(filas)
        render_ad_spend_cost_per_lead(gasto_raw, df_clientify)

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    traces = _plotly_traces(at)
    bar_trace, line_trace = traces[0], traces[1]
    assert list(bar_trace["x"]) == ["Marzo 2025", "Abril 2025"]
    assert bar_trace["textposition"] == "outside"
    assert list(line_trace["x"]) == ["Marzo 2025", "Abril 2025"]

    # Panel separado (make_subplots rows=2, cols=1): la barra vive en
    # x1/y1 (fila 1), la línea en x2/y2 (fila 2) — nunca comparten eje, así
    # que no pueden colisionar en altura de píxel sin importar el valor.
    # Ya no hace falta alternar "top"/"bottom center" — la línea siempre
    # usa "top center".
    assert bar_trace.get("yaxis") == "y"
    assert line_trace.get("yaxis") == "y2"
    assert line_trace["textposition"] == "top center"


def test_bar_y_linea_en_paneles_separados_en_todas_las_graficas_de_marketing():
    """Consistencia entre las 5 gráficas de barras+línea de "Marketing e
    Inversión": barra(s) y línea deben vivir en 2 PANELES APILADOS (ejes
    X/Y distintos, fila 1 vs fila 2) — nunca en el mismo panel con un eje Y
    secundario, que es lo que permitía que la línea tapara las etiquetas de
    valor de las barras (bug reportado 2026-10-07). La traza de barra(s) se
    mantiene en "outside" en todos los casos (sin cambios); la línea ya no
    necesita un `textposition` distinto por punto — con panel propio,
    "top center" fijo es suficiente."""
    def app_cost_per_lead():
        import pandas as pd
        from src.ui.sections.ad_spend_cost_per_lead import render_ad_spend_cost_per_lead
        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "800"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
        ])
        render_ad_spend_cost_per_lead(gasto_raw, df_clientify)

    def app_vs_closures():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_closures import render_ad_spend_vs_closures
        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "800"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
        ])
        render_ad_spend_vs_closures(gasto_raw, df_clientify)

    def app_roas():
        import pandas as pd
        from src.ui.sections.ad_spend_roas import render_ad_spend_roas
        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "300"},
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "400"},
        ])
        render_ad_spend_roas(gasto_raw, df_clientify)

    def app_total_roas():
        import pandas as pd
        from src.ui.sections.ad_spend_total_roas import render_ad_spend_total_roas
        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "300"},
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Cuota inicial pactada": "400"},
        ])
        render_ad_spend_total_roas(gasto_raw, df_clientify)

    def app_vs_process_value_roas():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_process_value_roas import render_ad_spend_vs_process_value_roas
        gasto_raw = pd.DataFrame([
            {"Fecha": "01/03/2025", "Divisa": "USD", "Importe": "100"},
            {"Fecha": "01/04/2025", "Divisa": "USD", "Importe": "200"},
        ])
        df_clientify = pd.DataFrame([
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-03-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": "3000"},
            {"estado": "activo", "Canal offline": "Clientify - Facebook",
             "Origen de la pauta": "Facebook", "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp("2025-04-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": "4000"},
        ])
        render_ad_spend_vs_process_value_roas(gasto_raw, df_clientify)

    casos = [
        ("ad_spend_cost_per_lead", app_cost_per_lead),
        ("ad_spend_vs_closures", app_vs_closures),
        ("ad_spend_roas", app_roas),
        ("ad_spend_total_roas", app_total_roas),
        ("ad_spend_vs_process_value_roas", app_vs_process_value_roas),
    ]

    for nombre, app_fn in casos:
        at = AppTest.from_function(app_fn)
        at.run()
        assert not at.exception, f"{nombre}: {at.exception}"

        traces = _plotly_traces(at)
        bar_traces = [t for t in traces if t.get("type") == "bar"]
        line_traces = [t for t in traces if t.get("type") == "scatter"]
        assert bar_traces and line_traces, f"{nombre}: faltan trazas de barra o línea"

        for bar in bar_traces:
            assert bar["textposition"] == "outside", f"{nombre}: la barra debe seguir en 'outside'"
            assert bar.get("yaxis", "y") == "y", f"{nombre}: la barra debe estar en el panel 1 (yaxis 'y')"

        for line in line_traces:
            assert line["textposition"] == "top center", (
                f"{nombre}: con panel propio, la línea ya no necesita alternar "
                f"'top'/'bottom center' — se encontró {line['textposition']!r}"
            )
            assert line.get("yaxis") == "y2", f"{nombre}: la línea debe estar en el panel 2 (yaxis 'y2')"


def test_render_ad_spend_barras_anchas_un_solo_trace_sin_importar_cantidad_de_meses():
    """Regresión: `render_ad_spend` usaba `px.bar(..., color="Mes_Año")`,
    que arma UN TRACE DE PLOTLY POR MES (mismo criterio en "x" y "color").
    Con `barmode` "group"/"relative" (default de Plotly), el ancho de cada
    barra se divide entre el número TOTAL de traces de la figura, así que
    con muchos meses (histórico largo, vía API de Meta) las barras quedaban
    minúsculas con mucho hueco alrededor — bug reportado por el usuario
    ("barras muy delgadas, con mucho espacio entre ellas", etiquetas
    diminutas). Fix: un único trace de barras, con un color por barra vía
    `marker_color` (lista), igual que el resto de "Marketing e Inversión"
    (ver `ad_spend_billed.py`). Se prueba con 9 meses (más que los 2-3 de
    otros tests) para que la regresión no pase inadvertida con pocos datos."""
    def app():
        from src.ui.sections.ad_spend import render_ad_spend
        from tests.test_ad_spend_sections_ui import _FakeUploadedFile

        filas = "\n".join(f"01/0{m}/2026,USD,{1000 + m * 300}" for m in range(1, 10))
        csv = ("Fecha,Divisa,Importe\n" + filas + "\n").encode()
        render_ad_spend([_FakeUploadedFile("billing.csv", csv)])

    at = AppTest.from_function(app)
    at.run()
    assert not at.exception

    chart = at.get("plotly_chart")[0]
    spec = json.loads(chart.proto.spec)
    traces = spec["data"]
    bar_traces = [t for t in traces if t.get("type") == "bar"]

    # Un solo trace de barras (NO uno por mes) — así Plotly no divide el
    # ancho de la barra entre 9 "grupos" vacíos.
    assert len(bar_traces) == 1
    assert len(bar_traces[0]["x"]) == 9

    # `bargap` moderado (no el 0.25 que, combinado con el bug de arriba,
    # dejaba aún menos ancho útil) y `barmode` que NO sea "group"/"relative"
    # con múltiples traces (acá es irrelevante por ser 1 solo trace, pero se
    # fija el valor para que una regresión futura a "color=Mes_Año" la
    # vuelva a disparar).
    assert spec["layout"]["bargap"] <= 0.2

    # Etiquetas de valor legibles (>= 12px) — antes no se fijaba `textfont`
    # y, combinado con el bug de las barras finas, Plotly las reducía más
    # de lo legible.
    textfont = bar_traces[0].get("textfont") or {}
    assert textfont.get("size", 0) >= 12

    # Un color distinto por barra (se conserva la intención visual original
    # de `color_discrete_sequence=px.colors.qualitative.Bold`).
    marker_colors = bar_traces[0]["marker"]["color"]
    assert len(set(marker_colors)) > 1


def test_graficas_de_barras_agrupadas_no_crean_un_trace_por_mes():
    """Mismo chequeo que el test de arriba, pero para las gráficas de
    "Marketing e Inversión" que SÍ necesitan más de 1 trace de barras
    (2 series comparadas) — deben seguir teniendo como máximo 1 trace POR
    SERIE (2), nunca 1 por mes, sin importar cuántos meses traiga el
    histórico."""
    def app_vs_revenue():
        import pandas as pd
        from src.ui.sections.ad_spend_vs_revenue import render_ad_spend_vs_revenue

        gasto_raw = pd.DataFrame([
            {"Fecha": f"01/0{m}/2025", "Divisa": "USD", "Importe": str(100 + m * 10)}
            for m in range(1, 8)
        ])
        df_clientify = pd.DataFrame([
            {"creado": pd.Timestamp(f"2025-0{m}-01"), "estado": "activo",
             "Canal offline": "Clientify - Facebook", "Origen de la pauta": "Facebook",
             "canal online": "paid social",
             "Fecha de cierre": pd.Timestamp(f"2025-0{m}-05"), "Fecha de segundo cierre": None,
             "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
             "Valor total del proceso": str(1000 + m * 50)}
            for m in range(1, 8)
        ])
        render_ad_spend_vs_revenue(gasto_raw, df_clientify)

    def app_billed():
        from src.ui.sections.ad_spend_billed import render_ad_spend_billed, CSV_MODE
        from tests.test_ad_spend_sections_ui import _FakeUploadedFile

        filas = "\n".join(f"01/0{m}/2026,USD,{500 + m * 50}" for m in range(1, 8))
        csv = ("Fecha,Divisa,Importe\n" + filas + "\n").encode()
        from src.ui.sections.ad_spend import load_ad_spend_files
        raw = load_ad_spend_files([_FakeUploadedFile("billing.csv", csv)])
        render_ad_spend_billed(CSV_MODE, csv_reuse_raw=raw)

    for nombre, app_fn, max_traces in [("vs_revenue", app_vs_revenue, 2), ("billed", app_billed, 1)]:
        at = AppTest.from_function(app_fn)
        at.run()
        assert not at.exception, f"{nombre}: {at.exception}"

        chart = at.get("plotly_chart")[0]
        spec = json.loads(chart.proto.spec)
        bar_traces = [t for t in spec["data"] if t.get("type") == "bar"]
        assert len(bar_traces) <= max_traces, (
            f"{nombre}: se esperaban como máximo {max_traces} trace(s) de "
            f"barras, se encontraron {len(bar_traces)} (¿un trace por mes?)"
        )
