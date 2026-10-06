"""Tests UI para `src/ui/sections/ad_spend_billed.py` — "Gasto facturado por
mes (cobros de Meta)", debajo del gasto real/en pauta. Usa
`streamlit.testing.v1.AppTest` (mismo harness/patrón que
`tests/test_ad_spend_sections_ui.py`). No pega a la API real: siempre se
fuerza `meta_ads_source` o `ad_spend_billed` según corresponda a no tener
token (forzando `CSV_MODE`/fallback) o se reemplaza la función cacheada
`_cached_fetch_meta_billed_amount` por un fake.
"""
import json

import pandas as pd
from streamlit.testing.v1 import AppTest


class _FakeUploadedFile:
    """Mínimo doble de `st.file_uploader`'s `UploadedFile` — solo lo que
    `load_ad_spend_files`/`AdSpendLoader` necesitan: `.name` y `.getvalue()`."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _fake_billed_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _plotly_traces(app_test: AppTest, index: int = 0) -> list[dict]:
    chart = app_test.get("plotly_chart")[index]
    spec = json.loads(chart.proto.spec)
    return spec["data"]


def _amounts_by_month(trace: dict) -> dict[str, float]:
    """`trace["y"]` viene serializado en binario (dtype/bdata) en versiones
    recientes de Plotly — se lee el monto desde `trace["text"]`
    ("$123.45"), siempre una lista plana de strings, mismo patrón que
    `tests/test_ad_spend_sections_ui.py`."""
    amounts = [float(t.replace("$", "").replace(",", "")) for t in trace["text"]]
    return dict(zip(trace["x"], amounts))


# --- CSV_MODE: reutiliza el CSV ya cargado arriba, sin uploader propio ---

def test_csv_mode_sin_datos_muestra_info_sin_uploader():
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_billed import render_ad_spend_billed, CSV_MODE
        render_ad_spend_billed(CSV_MODE, csv_reuse_raw=pd.DataFrame())

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    assert len(at.get("file_uploader")) == 0
    assert any("facturación" in i.value.lower() for i in at.info)


def test_csv_mode_con_datos_grafica_sin_uploader():
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_billed import render_ad_spend_billed, CSV_MODE
        billed = pd.DataFrame([
            {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "80"},
            {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "120"},
        ])
        render_ad_spend_billed(CSV_MODE, csv_reuse_raw=billed)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    assert len(at.get("file_uploader")) == 0
    traces = _plotly_traces(at)
    totals = _amounts_by_month(traces[0])
    assert totals == {"Marzo 2026": 80.0, "Abril 2026": 120.0}


# --- API_MODE: sin token configurado -> warning + expander con uploader obligatorio ---
#
# IMPORTANTE: `_cached_fetch_meta_billed_amount`/`META_ACCESS_TOKEN` se
# parchean con `monkeypatch.setattr` (NO con asignación directa dentro de
# `app()`) — `AppTest.from_function` ejecuta `app()` en el mismo proceso,
# así que una asignación directa deja el módulo real `ad_spend_billed`
# mutado para el resto de la sesión de pytest (ej. rompía
# `clear_meta_api_and_billing_cache()` en `test_meta_ads_source_ui.py`,
# llamado desde un test totalmente distinto). `monkeypatch` revierte
# automáticamente al terminar cada test.

def test_api_mode_sin_token_muestra_warning_y_expander_abierto_sin_cv(monkeypatch):
    from src.ui.sections import ad_spend_billed
    monkeypatch.setattr(ad_spend_billed, "META_ACCESS_TOKEN", "")

    def app():
        from src.ui.sections import ad_spend_billed
        ad_spend_billed.render_ad_spend_billed(ad_spend_billed.API_MODE)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    assert any("META_ACCESS_TOKEN" in w.value for w in at.warning)
    assert len(at.get("file_uploader")) == 1
    assert any("facturación" in i.value.lower() for i in at.info)
    assert len(at.get("plotly_chart")) == 0


def test_api_mode_sin_token_pero_con_csv_en_expander_grafica_con_csv(monkeypatch):
    from src.ui.sections import ad_spend_billed
    monkeypatch.setattr(ad_spend_billed, "META_ACCESS_TOKEN", "")

    csv = (
        "Fecha,Divisa,Importe\n"
        "01/03/2026,USD,80\n"
    ).encode("utf-8")

    def app():
        from src.ui.sections import ad_spend_billed
        ad_spend_billed.render_ad_spend_billed(ad_spend_billed.API_MODE)

    at = AppTest.from_function(app)
    at.run(timeout=15)
    at.get("file_uploader")[0].upload("facturacion.csv", csv, "text/csv").run(timeout=15)

    assert not at.exception
    traces = _plotly_traces(at)
    totals = _amounts_by_month(traces[0])
    assert totals == {"Marzo 2026": 80.0}


# --- API_MODE: fetch exitoso (mockeado) ---

def test_api_mode_fetch_exitoso_muestra_grafico_sin_csv_cargado(monkeypatch):
    """Caso pedido explícitamente: fuente API, SIN CSV cargado — el gráfico
    debe mostrarse igual, usando los datos de la API."""
    from src.ui.sections import ad_spend_billed
    monkeypatch.setattr(ad_spend_billed, "META_ACCESS_TOKEN", "fake-token-api-mode-test")

    df = _fake_billed_df([
        {"Fecha": pd.Timestamp("2026-08-01"), "Divisa": "USD", "Importe": 4589.12,
         "Año": 2026, "Mes_num": 8, "Mes_Año": "Agosto 2026"},
        {"Fecha": pd.Timestamp("2026-09-01"), "Divisa": "USD", "Importe": 3726.20,
         "Año": 2026, "Mes_num": 9, "Mes_Año": "Septiembre 2026"},
    ])
    monkeypatch.setattr(
        ad_spend_billed, "_cached_fetch_meta_billed_amount",
        lambda token, since, until: (df, [], "2026-10-06 10:00:00"),
    )

    def app():
        from src.ui.sections import ad_spend_billed
        ad_spend_billed.render_ad_spend_billed(ad_spend_billed.API_MODE)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    assert len(at.get("plotly_chart")) == 1
    traces = _plotly_traces(at)
    totals = _amounts_by_month(traces[0])
    assert totals["Agosto 2026"] == 4589.12
    assert totals["Septiembre 2026"] == 3726.20
    captions = [c.value for c in at.caption]
    assert any("2026-08-01" in c and "2026-09-01" in c for c in captions)
    assert any("2026-10-06 10:00:00" in c for c in captions)
    # El expander de comparación existe pero es secundario/opcional.
    assert any("Comparar contra CSV" in e.label for e in at.expander)


def test_api_mode_fetch_exitoso_con_csv_en_expander_muestra_comparacion_sin_cambiar_grafico_principal(monkeypatch):
    from src.ui.sections import ad_spend_billed
    monkeypatch.setattr(ad_spend_billed, "META_ACCESS_TOKEN", "fake-token-api-mode-test-2")

    df = _fake_billed_df([
        {"Fecha": pd.Timestamp("2026-08-01"), "Divisa": "USD", "Importe": 4589.12,
         "Año": 2026, "Mes_num": 8, "Mes_Año": "Agosto 2026"},
    ])
    monkeypatch.setattr(
        ad_spend_billed, "_cached_fetch_meta_billed_amount",
        lambda token, since, until: (df, [], "2026-10-06 10:00:00"),
    )

    csv = ("Fecha,Divisa,Importe\n01/08/2026,USD,4500\n").encode("utf-8")

    def app():
        from src.ui.sections import ad_spend_billed
        ad_spend_billed.render_ad_spend_billed(ad_spend_billed.API_MODE)

    at = AppTest.from_function(app)
    at.run(timeout=15)
    at.get("file_uploader")[0].upload("facturacion.csv", csv, "text/csv").run(timeout=15)

    assert not at.exception
    # El gráfico principal sigue usando la API (4589.12), no el CSV (4500).
    traces = _plotly_traces(at)
    totals = _amounts_by_month(traces[0])
    assert totals["Agosto 2026"] == 4589.12
    captions = [c.value for c in at.caption]
    assert any("4,589.12" in c and "4,500.00" in c for c in captions)


def test_api_mode_cuenta_fallida_muestra_warning_sin_tumbar(monkeypatch):
    from src.ui.sections import ad_spend_billed
    monkeypatch.setattr(ad_spend_billed, "META_ACCESS_TOKEN", "fake-token-api-mode-warning")

    df = _fake_billed_df([
        {"Fecha": pd.Timestamp("2026-08-01"), "Divisa": "USD", "Importe": 100.0,
         "Año": 2026, "Mes_num": 8, "Mes_Año": "Agosto 2026"},
    ])
    warnings = ["Meta Ads (facturado) — cuenta 'Contingencia': timeout"]
    monkeypatch.setattr(
        ad_spend_billed, "_cached_fetch_meta_billed_amount",
        lambda token, since, until: (df, warnings, "t"),
    )

    def app():
        from src.ui.sections import ad_spend_billed
        ad_spend_billed.render_ad_spend_billed(ad_spend_billed.API_MODE)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    assert any("Contingencia" in w.value for w in at.warning)
    assert len(at.get("plotly_chart")) == 1


def test_api_mode_fetch_lanza_error_cae_a_csv_del_expander(monkeypatch):
    from src.ui.sections import ad_spend_billed
    monkeypatch.setattr(ad_spend_billed, "META_ACCESS_TOKEN", "fake-token-api-mode-fails")

    def _raise(token, since, until):
        raise ad_spend_billed.MetaAdsAPIError("error simulado de red")

    monkeypatch.setattr(ad_spend_billed, "_cached_fetch_meta_billed_amount", _raise)

    csv = ("Fecha,Divisa,Importe\n01/03/2026,USD,80\n").encode("utf-8")

    def app():
        from src.ui.sections import ad_spend_billed
        ad_spend_billed.render_ad_spend_billed(ad_spend_billed.API_MODE)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    assert any("error simulado de red" in w.value for w in at.warning)
    assert len(at.get("file_uploader")) == 1

    at.get("file_uploader")[0].upload("facturacion.csv", csv, "text/csv").run(timeout=15)
    assert not at.exception
    traces = _plotly_traces(at)
    totals = _amounts_by_month(traces[0])
    assert totals == {"Marzo 2026": 80.0}


# --- Comparación opcional real vs facturado (independiente de API/CSV) ---

def test_con_real_raw_agrega_segunda_barra_de_comparacion():
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_billed import render_ad_spend_billed, CSV_MODE

        billed = pd.DataFrame([{"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "80"}])
        real = pd.DataFrame([{"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "100"}])
        render_ad_spend_billed(CSV_MODE, csv_reuse_raw=billed, real_raw=real)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    traces = _plotly_traces(at)
    assert len(traces) == 2
    names = {t["name"] for t in traces}
    assert names == {"Facturado (USD)", "Gasto real (USD)"}
    assert any("Real" in e.label and "Facturado" in e.label for e in at.expander)


def test_sin_real_raw_no_hay_comparacion_ni_expander_de_diferencia():
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend_billed import render_ad_spend_billed, CSV_MODE

        billed = pd.DataFrame([{"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "80"}])
        render_ad_spend_billed(CSV_MODE, csv_reuse_raw=billed)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    traces = _plotly_traces(at)
    assert len(traces) == 1
    assert len(at.expander) == 0


# --- La gráfica nueva aparece DEBAJO de la de gasto real (orden en TAB 1) ---

def test_grafica_facturado_aparece_debajo_de_la_de_gasto_real():
    def app():
        import pandas as pd
        from src.ui.sections.ad_spend import render_ad_spend_from_raw
        from src.ui.sections.ad_spend_billed import render_ad_spend_billed, CSV_MODE

        real = pd.DataFrame([{"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "100"}])
        billed = pd.DataFrame([{"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "80"}])
        render_ad_spend_from_raw(real)
        render_ad_spend_billed(CSV_MODE, csv_reuse_raw=billed, real_raw=real)

    at = AppTest.from_function(app)
    at.run(timeout=15)

    assert not at.exception
    headers = [m.value for m in at.markdown if m.value.startswith("###")]
    idx_real = next(i for i, h in enumerate(headers) if "Gasto en pauta publicitaria" in h)
    idx_facturado = next(i for i, h in enumerate(headers) if "Gasto facturado por mes" in h)
    assert idx_facturado > idx_real
    assert len(at.get("plotly_chart")) == 2
