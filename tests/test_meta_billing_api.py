"""Tests de `src/data_sources/meta_billing_api.py` — cliente de COBROS
reales de Meta Ads vía `/act_{id}/activities`. Sin red real: todo contra un
`requests.Session` fake inyectado vía monkeypatch de `_build_session`,
mismo patrón que `tests/test_meta_ads_api.py`.
"""
import json
import re

import pandas as pd
import pytest
import requests

from src.analytics.ad_spend import FECHA_COL, DIVISA_COL, IMPORTE_COL
from src.data_sources import meta_billing_api as api


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} Client Error", response=self)

    def json(self):
        return self.payload


def _account_id_from_url(url: str) -> str | None:
    m = re.search(r"act_(\w+)", url)
    return m.group(1) if m else None


class _FakeSession:
    def __init__(self, responses_by_account, always_fail_for=None, error_message="falla de red simulada"):
        self.responses_by_account = {k: list(v) for k, v in responses_by_account.items()}
        self.always_fail_for = set(always_fail_for or set())
        self.error_message = error_message
        self.calls: list[str] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        account_id = _account_id_from_url(url)
        if account_id in self.always_fail_for:
            raise requests.exceptions.ConnectionError(self.error_message)
        queue = self.responses_by_account[account_id]
        payload = queue.pop(0)
        return _FakeResponse(payload)


def _patch(monkeypatch, fake_session):
    monkeypatch.setattr(api, "_build_session", lambda token: fake_session)
    import src.data_sources.meta_ads_api as meta_ads_api
    monkeypatch.setattr(meta_ads_api.time, "sleep", lambda seconds: None)


def _event(event_type: str, event_time: str, extra_data: dict | None = None) -> dict:
    return {
        "event_type": event_type,
        "event_time": event_time,
        "extra_data": json.dumps(extra_data) if extra_data is not None else "{}",
    }


def _billing_event(event_time: str, cents: int, currency: str = "USD", transaction_id: str = "tx1") -> dict:
    return _event(
        api.BILLING_CHARGE_EVENT, event_time,
        {"currency": currency, "new_value": cents, "transaction_id": transaction_id, "type": "payment_amount"},
    )


# --- Conversión de centavos a dólares + filtro de event_type ---

def test_extract_billing_charges_convierte_centavos_a_dolares():
    records = [_billing_event("2026-08-01T12:00:00+0000", 458912, transaction_id="tx1")]
    warnings: list[str] = []
    charges = api._extract_billing_charges(records, "Interna", warnings)
    assert charges == [{"event_time": "2026-08-01T12:00:00+0000", "amount": 4589.12, "transaction_id": "tx1"}]
    assert warnings == []


def test_extract_billing_charges_ignora_otros_tipos_de_evento():
    records = [
        _event("update_ad_run_status", "2026-08-01T12:00:00+0000", {"old_value": "x"}),
        _event("create_audience", "2026-08-01T12:05:00+0000", {"name": "aud"}),
        _billing_event("2026-08-01T12:10:00+0000", 90000, transaction_id="tx2"),
    ]
    warnings: list[str] = []
    charges = api._extract_billing_charges(records, "Interna", warnings)
    assert len(charges) == 1
    assert charges[0]["transaction_id"] == "tx2"
    assert charges[0]["amount"] == 900.0


def test_extract_billing_charges_moneda_distinta_a_usd_se_descarta_con_warning():
    records = [
        _billing_event("2026-08-01T12:00:00+0000", 10000, currency="COP", transaction_id="tx_cop"),
        _billing_event("2026-08-02T12:00:00+0000", 50000, currency="USD", transaction_id="tx_usd"),
    ]
    warnings: list[str] = []
    charges = api._extract_billing_charges(records, "Soluciones Migratorias", warnings)
    assert len(charges) == 1
    assert charges[0]["transaction_id"] == "tx_usd"
    assert len(warnings) == 1
    assert "COP" in warnings[0]
    assert "tx_cop" in warnings[0]
    assert "Soluciones Migratorias" in warnings[0]


def test_extract_billing_charges_evento_sin_transaction_id_se_ignora():
    records = [_event(api.BILLING_CHARGE_EVENT, "2026-08-01T12:00:00+0000", {"currency": "USD", "new_value": 100})]
    warnings: list[str] = []
    charges = api._extract_billing_charges(records, "Interna", warnings)
    assert charges == []
    assert warnings == []


# --- Deduplicación por transaction_id ---

def test_build_billed_dataframe_deduplica_por_transaction_id():
    charges = [
        {"event_time": "2026-08-01T12:00:00+0000", "amount": 900.0, "transaction_id": "tx1"},
        {"event_time": "2026-08-01T12:00:00+0000", "amount": 900.0, "transaction_id": "tx1"},  # repetida
        {"event_time": "2026-08-02T12:00:00+0000", "amount": 100.0, "transaction_id": "tx2"},
    ]
    out = api._build_billed_dataframe(charges)
    assert out[IMPORTE_COL].sum() == pytest.approx(1000.0)  # NO 1900
    assert len(out) == 2  # tx1 una sola vez (mismo día -> 1 fila), tx2 otra


# --- Conversión UTC -> America/Bogota antes de agrupar por mes ---

def test_conversion_utc_a_bogota_cobro_cerca_del_cambio_de_mes():
    """2026-09-30 23:30 Bogotá (UTC-5) = 2026-10-01 04:30 UTC — debe contar
    en SEPTIEMBRE, no en octubre, si la conversión de zona se hace ANTES de
    extraer el mes."""
    charges = [{"event_time": "2026-10-01T04:30:00+0000", "amount": 100.0, "transaction_id": "tx_boundary"}]
    out = api._build_billed_dataframe(charges)
    assert len(out) == 1
    assert out.iloc[0]["Mes_Año"] == "Septiembre 2026"
    assert out.iloc[0][FECHA_COL] == pd.Timestamp("2026-09-30 23:30:00")


def test_build_billed_dataframe_vacio_devuelve_columnas_esperadas():
    out = api._build_billed_dataframe([])
    assert out.empty
    assert list(out.columns) == api._PREPARED_COLUMNS


def test_build_billed_dataframe_divisa_siempre_usd():
    charges = [{"event_time": "2026-08-01T12:00:00+0000", "amount": 100.0, "transaction_id": "tx1"}]
    out = api._build_billed_dataframe(charges)
    assert (out[DIVISA_COL] == "USD").all()


# --- Esquema idéntico al del CSV / meta_ads_api ---

def test_esquema_de_salida_coincide_con_prepare_ad_spend():
    from src.analytics import ad_spend

    charges = [
        {"event_time": "2026-03-01T12:00:00+0000", "amount": 100.0, "transaction_id": "tx1"},
        {"event_time": "2026-03-15T12:00:00+0000", "amount": 200.0, "transaction_id": "tx2"},
    ]
    out = api._build_billed_dataframe(charges)
    assert list(out.columns) == [FECHA_COL, DIVISA_COL, IMPORTE_COL, "Año", "Mes_num", "Mes_Año"]
    assert out[FECHA_COL].dtype.kind == "M"
    assert out[IMPORTE_COL].dtype.kind == "f"

    reprepared = ad_spend.prepare_ad_spend(out)
    assert reprepared[IMPORTE_COL].sum() == pytest.approx(out[IMPORTE_COL].sum())
    monthly = ad_spend.monthly_ad_spend(out)
    assert monthly["Importe"].sum() == pytest.approx(300.0)


# --- fetch_meta_billed_amount: paralelo + falla parcial de una cuenta ---

def test_fetch_meta_billed_amount_combina_3_cuentas(monkeypatch):
    accounts = [("Cuenta A", "111"), ("Cuenta B", "222"), ("Cuenta C", "333")]
    responses = {
        "111": [{"data": [_billing_event("2026-08-01T12:00:00+0000", 10000, transaction_id="a1")], "paging": {}}],
        "222": [{"data": [_billing_event("2026-08-01T12:00:00+0000", 20000, transaction_id="b1")], "paging": {}}],
        "333": [{"data": [_billing_event("2026-08-01T12:00:00+0000", 30000, transaction_id="c1")], "paging": {}}],
    }
    fake_session = _FakeSession(responses)
    _patch(monkeypatch, fake_session)

    df, warnings = api.fetch_meta_billed_amount(
        token="fake-token", since="2026-01-01", until="2026-12-31", accounts=accounts, max_workers=3,
    )

    assert warnings == []
    assert df[IMPORTE_COL].sum() == pytest.approx(600.0)


def test_fetch_meta_billed_amount_una_cuenta_falla_no_tumba_las_otras(monkeypatch):
    accounts = [("Cuenta A", "111"), ("Cuenta B - sin permiso", "222")]
    responses = {"111": [{"data": [_billing_event("2026-08-01T12:00:00+0000", 10000, transaction_id="a1")], "paging": {}}]}
    fake_session = _FakeSession(responses, always_fail_for={"222"})
    _patch(monkeypatch, fake_session)

    df, warnings = api.fetch_meta_billed_amount(
        token="fake-token", since="2026-01-01", until="2026-12-31", accounts=accounts, max_workers=2,
    )

    assert df[IMPORTE_COL].sum() == pytest.approx(100.0)
    assert len(warnings) == 1
    assert "Cuenta B - sin permiso" in warnings[0]


def test_fetch_meta_billed_amount_sin_token_lanza_error_claro():
    with pytest.raises(api.MetaAdsAPIError):
        api.fetch_meta_billed_amount(token="", accounts=[("Cuenta A", "111")])


# --- El token nunca aparece en warnings/errores ---

def test_el_token_nunca_aparece_en_los_warnings(monkeypatch):
    token = "EAASECRETOQUEJAMASDEBEAPARECER"
    accounts = [("Cuenta Fallida", "999")]
    fake_session = _FakeSession({}, always_fail_for={"999"}, error_message=f"falló con Authorization: Bearer {token}")
    _patch(monkeypatch, fake_session)

    df, warnings = api.fetch_meta_billed_amount(
        token=token, since="2026-01-01", until="2026-12-31", accounts=accounts, max_workers=1,
    )

    assert len(warnings) == 1
    assert token not in warnings[0]
    assert "***" in warnings[0]


# --- MetaBillingAPIClient ---

def test_meta_billing_api_client_sin_token_lanza_error_claro():
    with pytest.raises(api.MetaAdsAPIError):
        api.MetaBillingAPIClient(token="")


def test_meta_billing_api_client_load_expone_warnings(monkeypatch):
    accounts = [("Cuenta A", "111"), ("Cuenta B", "222")]
    responses = {"111": [{"data": [_billing_event("2026-08-01T12:00:00+0000", 10000, transaction_id="a1")], "paging": {}}]}
    fake_session = _FakeSession(responses, always_fail_for={"222"})
    _patch(monkeypatch, fake_session)

    client = api.MetaBillingAPIClient(token="fake-token", accounts=accounts, since="2026-01-01", until="2026-12-31", max_workers=2)
    assert client.warnings == []

    df = client.load()

    assert df[IMPORTE_COL].sum() == pytest.approx(100.0)
    assert len(client.warnings) == 1
