"""Tests de `src/data_sources/meta_ads_api.py` — cliente de la Meta
Marketing API (Insights, gasto real diario). Sin red real: todo contra un
`requests.Session` fake inyectado vía monkeypatch de `_build_session`,
mismo patrón que `tests/test_clientify_api_pagination.py`.
"""
import re

import pandas as pd
import pytest
import requests

from src.analytics.ad_spend import FECHA_COL, DIVISA_COL, IMPORTE_COL
from src.data_sources import meta_ads_api as api


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Client Error", response=self
            )

    def json(self):
        return self.payload


def _account_id_from_url(url: str) -> str | None:
    m = re.search(r"act_(\w+)", url)
    return m.group(1) if m else None


class _FakeSession:
    """`responses_by_account`: dict account_id -> lista de payloads (dicts),
    consumidos en orden a medida que se pide cada página. `fail_count_for`:
    dict account_id -> cuántas veces debe fallar con un error de red ANTES
    de responder normal (simula un blip transitorio que se recupera con
    retry). `always_fail_for`: set de account_ids que SIEMPRE fallan.
    `error_message`: mensaje de la excepción simulada, para poder incluir
    un token-looking string en el test de sanitización."""

    def __init__(self, responses_by_account, fail_count_for=None, always_fail_for=None, error_message="falla de red simulada"):
        self.responses_by_account = {k: list(v) for k, v in responses_by_account.items()}
        self.fail_count_for = dict(fail_count_for or {})
        self.always_fail_for = set(always_fail_for or set())
        self.error_message = error_message
        self.calls: list[str] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        account_id = _account_id_from_url(url)

        if account_id in self.always_fail_for:
            raise requests.exceptions.ConnectionError(self.error_message)

        remaining = self.fail_count_for.get(account_id, 0)
        if remaining > 0:
            self.fail_count_for[account_id] = remaining - 1
            raise requests.exceptions.ConnectionError(self.error_message)

        queue = self.responses_by_account[account_id]
        payload = queue.pop(0)
        return _FakeResponse(payload)


def _patch(monkeypatch, fake_session):
    monkeypatch.setattr(api, "_build_session", lambda token: fake_session)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)


# --- Conversión de spend (punto decimal, no coma europea) ---

def test_parse_spend_punto_decimal():
    assert api._parse_spend("123.45") == 123.45
    assert api._parse_spend("0") == 0.0
    assert api._parse_spend(None) == 0.0
    assert api._parse_spend("") == 0.0
    assert api._parse_spend("no-es-numero") == 0.0


def test_parse_spend_no_reinterpreta_coma_como_decimal_europeo():
    """A diferencia de `ad_spend._clean_importe`, acá una coma NO debe
    tratarse como separador decimal europeo — el Graph API no la usa así."""
    assert api._parse_spend("1234.56") == 1234.56


# --- Paginación: paging.next ---

def test_fetch_account_insights_sigue_paging_next_hasta_agotar_paginas(monkeypatch):
    acc = "111"
    responses = {
        acc: [
            {"data": [{"date_start": "2026-01-01", "spend": "10.00"}],
             "paging": {"next": f"https://graph.facebook.com/v26.0/act_{acc}/insights?after=X"}},
            {"data": [{"date_start": "2026-01-02", "spend": "20.00"}], "paging": {}},
        ]
    }
    fake_session = _FakeSession(responses)
    _patch(monkeypatch, fake_session)

    records = api._fetch_account_insights("fake-token", acc, "2026-01-01", "2026-01-02")

    assert [r["date_start"] for r in records] == ["2026-01-01", "2026-01-02"]
    assert len(fake_session.calls) == 2


def test_fetch_account_insights_una_sola_pagina_no_sigue_de_mas(monkeypatch):
    acc = "222"
    responses = {acc: [{"data": [{"date_start": "2026-01-01", "spend": "5.00"}], "paging": {}}]}
    fake_session = _FakeSession(responses)
    _patch(monkeypatch, fake_session)

    records = api._fetch_account_insights("fake-token", acc, "2026-01-01", "2026-01-01")

    assert len(records) == 1
    assert len(fake_session.calls) == 1


def test_fetch_account_insights_sigue_cursors_after_si_no_hay_paging_next(monkeypatch):
    acc = "333"
    responses = {
        acc: [
            {"data": [{"date_start": "2026-01-01", "spend": "10.00"}],
             "paging": {"cursors": {"after": "CURSOR1"}}},
            {"data": [{"date_start": "2026-01-02", "spend": "20.00"}], "paging": {}},
        ]
    }
    fake_session = _FakeSession(responses)
    _patch(monkeypatch, fake_session)

    records = api._fetch_account_insights("fake-token", acc, "2026-01-01", "2026-01-02")

    assert [r["date_start"] for r in records] == ["2026-01-01", "2026-01-02"]
    assert len(fake_session.calls) == 2
    # La 2da llamada reusa la URL base (no paging.next) con 'after' agregado.
    assert fake_session.calls[1] == fake_session.calls[0]


# --- Retries con backoff ---

def test_fetch_account_insights_se_recupera_de_una_falla_transitoria(monkeypatch):
    acc = "444"
    responses = {acc: [{"data": [{"date_start": "2026-01-01", "spend": "1.00"}], "paging": {}}]}
    fake_session = _FakeSession(responses, fail_count_for={acc: 1})
    _patch(monkeypatch, fake_session)

    records = api._fetch_account_insights("fake-token", acc, "2026-01-01", "2026-01-01")

    assert len(records) == 1
    assert len(fake_session.calls) == 2  # 1 falla + 1 reintento exitoso


def test_fetch_account_insights_agota_reintentos_y_propaga_error_sanitizado(monkeypatch):
    acc = "555"
    token = "EAATHISISASECRETTOKEN123"
    fake_session = _FakeSession(
        {acc: []}, always_fail_for={acc}, error_message=f"conexión falló con Authorization: Bearer {token}"
    )
    _patch(monkeypatch, fake_session)

    with pytest.raises(api.MetaAdsAPIError) as exc_info:
        api._fetch_account_insights(token, acc, "2026-01-01", "2026-01-01")

    assert len(fake_session.calls) == api.MAX_RETRIES
    assert token not in str(exc_info.value)
    assert "***" in str(exc_info.value)


def test_backoff_duerme_1s_y_2s_entre_reintentos(monkeypatch):
    acc = "666"
    fake_session = _FakeSession({acc: []}, always_fail_for={acc})
    monkeypatch.setattr(api, "_build_session", lambda token: fake_session)

    sleeps: list[float] = []
    monkeypatch.setattr(api.time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(api.MetaAdsAPIError):
        api._fetch_account_insights("fake-token", acc, "2026-01-01", "2026-01-01")

    assert sleeps == [1, 2]


# --- Suma por día entre varias cuentas ---

def test_build_daily_dataframe_suma_varias_cuentas_por_dia():
    frame_a = api._account_records_to_df([
        {"date_start": "2026-01-01", "spend": "100.00"},
        {"date_start": "2026-01-02", "spend": "50.00"},
    ])
    frame_b = api._account_records_to_df([
        {"date_start": "2026-01-01", "spend": "25.50"},
    ])
    frame_c = api._account_records_to_df([])  # cuenta sin datos en el rango

    out = api._build_daily_dataframe([frame_a, frame_b, frame_c])

    row_0101 = out[out[FECHA_COL] == pd.Timestamp("2026-01-01")]
    row_0102 = out[out[FECHA_COL] == pd.Timestamp("2026-01-02")]
    assert row_0101[IMPORTE_COL].iloc[0] == pytest.approx(125.50)
    assert row_0102[IMPORTE_COL].iloc[0] == pytest.approx(50.00)
    assert (out[DIVISA_COL] == "USD").all()


def test_build_daily_dataframe_todas_las_cuentas_vacias_devuelve_df_vacio_con_columnas():
    out = api._build_daily_dataframe([pd.DataFrame(columns=["date_start", "spend"])])
    assert out.empty
    assert list(out.columns) == api._PREPARED_COLUMNS


# --- Esquema idéntico al de ad_spend.prepare_ad_spend ---

def test_esquema_de_salida_es_compatible_con_prepare_ad_spend():
    from src.analytics import ad_spend

    frame = api._account_records_to_df([
        {"date_start": "2026-03-01", "spend": "100.00"},
        {"date_start": "2026-03-02", "spend": "200.00"},
    ])
    out = api._build_daily_dataframe([frame])

    assert list(out.columns) == [FECHA_COL, DIVISA_COL, IMPORTE_COL, "Año", "Mes_num", "Mes_Año"]
    assert out[FECHA_COL].dtype.kind == "M"  # datetime64
    assert out[IMPORTE_COL].dtype.kind == "f"  # float

    # prepare_ad_spend es idempotente sobre esta salida: re-aplicarla no
    # debe perder filas ni cambiar el total de Importe.
    reprepared = ad_spend.prepare_ad_spend(out)
    assert reprepared[IMPORTE_COL].sum() == pytest.approx(out[IMPORTE_COL].sum())
    assert len(reprepared) == len(out)

    # Y las 6 gráficas que reciben "gasto_raw" ya preparado siguen andando:
    monthly = ad_spend.monthly_ad_spend(out)
    assert monthly["Importe"].sum() == pytest.approx(300.0)


# --- fetch_meta_ad_spend: paralelo + falla parcial de una cuenta ---

def test_fetch_meta_ad_spend_combina_3_cuentas_en_paralelo(monkeypatch):
    accounts = [("Cuenta A", "111"), ("Cuenta B", "222"), ("Cuenta C", "333")]
    responses = {
        "111": [{"data": [{"date_start": "2026-01-01", "spend": "10.00"}], "paging": {}}],
        "222": [{"data": [{"date_start": "2026-01-01", "spend": "20.00"}], "paging": {}}],
        "333": [{"data": [{"date_start": "2026-01-01", "spend": "30.00"}], "paging": {}}],
    }
    fake_session = _FakeSession(responses)
    _patch(monkeypatch, fake_session)

    df, warnings = api.fetch_meta_ad_spend(
        token="fake-token", since="2026-01-01", until="2026-01-01", accounts=accounts, max_workers=3,
    )

    assert warnings == []
    assert df[IMPORTE_COL].sum() == pytest.approx(60.0)


def test_fetch_meta_ad_spend_una_cuenta_falla_no_tumba_las_otras(monkeypatch):
    accounts = [("Cuenta A", "111"), ("Cuenta B - sin permiso", "222")]
    responses = {"111": [{"data": [{"date_start": "2026-01-01", "spend": "10.00"}], "paging": {}}]}
    fake_session = _FakeSession(responses, always_fail_for={"222"})
    _patch(monkeypatch, fake_session)

    df, warnings = api.fetch_meta_ad_spend(
        token="fake-token", since="2026-01-01", until="2026-01-01", accounts=accounts, max_workers=2,
    )

    assert df[IMPORTE_COL].sum() == pytest.approx(10.0)
    assert len(warnings) == 1
    assert "Cuenta B - sin permiso" in warnings[0]


def test_fetch_meta_ad_spend_todas_las_cuentas_fallan_devuelve_df_vacio_sin_excepcion(monkeypatch):
    accounts = [("Cuenta A", "111"), ("Cuenta B", "222")]
    fake_session = _FakeSession({}, always_fail_for={"111", "222"})
    _patch(monkeypatch, fake_session)

    df, warnings = api.fetch_meta_ad_spend(
        token="fake-token", since="2026-01-01", until="2026-01-01", accounts=accounts, max_workers=2,
    )

    assert df.empty
    assert len(warnings) == 2


def test_fetch_meta_ad_spend_sin_token_lanza_error_claro():
    with pytest.raises(api.MetaAdsAPIError):
        api.fetch_meta_ad_spend(token="", accounts=[("Cuenta A", "111")])


# --- El token nunca aparece en un mensaje de error/warning ---

def test_el_token_nunca_aparece_en_los_warnings(monkeypatch):
    token = "EAASECRETOQUENUNCADEBESALIR999"
    accounts = [("Cuenta Fallida", "999")]
    fake_session = _FakeSession(
        {}, always_fail_for={"999"}, error_message=f"error llamando con header Authorization: Bearer {token}"
    )
    _patch(monkeypatch, fake_session)

    df, warnings = api.fetch_meta_ad_spend(
        token=token, since="2026-01-01", until="2026-01-01", accounts=accounts, max_workers=1,
    )

    assert len(warnings) == 1
    assert token not in warnings[0]
    assert "***" in warnings[0]


def test_sanitize_reemplaza_el_token_por_asteriscos():
    token = "EAASUPERSECRETO"
    msg = f"request falló: Authorization: Bearer {token} en la URL"
    sanitized = api._sanitize(msg, token)
    assert token not in sanitized
    assert "***" in sanitized


def test_build_session_usa_header_authorization_bearer_no_query_string():
    session = api._build_session("mi-token-de-prueba")
    assert session.headers.get("Authorization") == "Bearer mi-token-de-prueba"
    # Nada de access_token en session.params (a diferencia del diagnóstico).
    assert not getattr(session, "params", None)


# --- MetaAdsAPIClient (wrapper de clase) ---

def test_meta_ads_api_client_sin_token_lanza_error_claro():
    with pytest.raises(api.MetaAdsAPIError):
        api.MetaAdsAPIClient(token="")


def test_meta_ads_api_client_load_expone_warnings_tras_falla_parcial(monkeypatch):
    accounts = [("Cuenta A", "111"), ("Cuenta B", "222")]
    responses = {"111": [{"data": [{"date_start": "2026-01-01", "spend": "10.00"}], "paging": {}}]}
    fake_session = _FakeSession(responses, always_fail_for={"222"})
    _patch(monkeypatch, fake_session)

    client = api.MetaAdsAPIClient(token="fake-token", accounts=accounts, since="2026-01-01", until="2026-01-01", max_workers=2)
    assert client.warnings == []  # nada hasta que se llame load()

    df = client.load()

    assert df[IMPORTE_COL].sum() == pytest.approx(10.0)
    assert len(client.warnings) == 1
