"""Tests del cache en disco de `ClientifyAPIClient` (src/data_sources/clientify_api.py).

Contexto: el plan original era un sync INCREMENTAL de verdad, filtrando
`GET /contacts/` por fecha de modificación (`?modified__gte=`), con una rama
separada `_fetch_contacts_since` que se activaba una vez que ya había cache
en disco. Confirmado empíricamente que esta cuenta IGNORA ese filtro (y 10
variantes de nombre más) en silencio — siempre devuelve el mismo `count`
sin importar el filtro — y además esa rama era SECUENCIAL (sin los workers
en paralelo del full sync), por lo que cada sync posterior al primero
tardaba muchos minutos más sin ningún beneficio real a cambio (ver
auditoría de performance, octubre 2026, en el docstring del módulo). Esa
rama y `_fetch_contacts_since` fueron eliminadas por completo: ahora TODO
sync (primero o posterior) usa `_fetch_all_contacts` (paralelo).

Estos tests verifican lo que sigue siendo responsabilidad de esta capa:
  1. el cache en disco persiste entre "sesiones" (sobrevive un reinicio
     simulado del proceso),
  2. CUALQUIER sync (con o sin cache previo en disco) llama a
     `_fetch_all_contacts`, nunca a una rama distinta,
  3. el upsert por `_contact_id` reemplaza filas existentes en vez de
     duplicarlas, y agrega las nuevas,
  4. un cache corrupto/vacío no rompe el flujo (se fusiona igual, sin datos
     previos que aportar).
"""
import pandas as pd
import pytest

from src.data_sources import clientify_api as api


def _contact(contact_id: int, owner_name: str, created: str = "2026-06-03T00:20:51+02:00") -> dict:
    return {
        "id": contact_id,
        "owner_name": owner_name,
        "medium": "",
        "contact_source": {},
        "tags": [],
        "custom_fields": [],
        "created": created,
    }


@pytest.fixture(autouse=True)
def _isolated_cache_paths(tmp_path, monkeypatch):
    """Redirige el cache en disco a un directorio temporal — ningún test
    toca `data/cache/` real."""
    monkeypatch.setattr(api, "CONTACTS_CACHE_PATH", tmp_path / "contacts_cache.parquet")
    monkeypatch.setattr(api, "CACHE_DIR", tmp_path)


# --- _upsert_contacts_df: lo más importante a probar primero, sin red ---

def test_upsert_sin_cache_previo_devuelve_new_df_tal_cual():
    new_df = api._build_and_normalize_indexed([_contact(1, "ana perdomo")])
    result = api._upsert_contacts_df(None, new_df)
    pd.testing.assert_frame_equal(result, new_df)


def test_upsert_agrega_contactos_nuevos_sin_perder_los_existentes():
    cached_df = api._build_and_normalize_indexed([_contact(1, "ana perdomo"), _contact(2, "uriel ortega")])
    new_df = api._build_and_normalize_indexed([_contact(3, "sebastian ortega")])

    result = api._upsert_contacts_df(cached_df, new_df)

    assert len(result) == 3
    assert set(result.index) == {1, 2, 3}


def test_upsert_reemplaza_fila_existente_sin_duplicar():
    cached_df = api._build_and_normalize_indexed([_contact(1, "ana perdomo")])
    new_df = api._build_and_normalize_indexed([_contact(1, "sebastian ortega")])  # mismo ID, owner cambiado

    result = api._upsert_contacts_df(cached_df, new_df)

    assert len(result) == 1  # no duplica
    assert result.loc[1, "propietario"] == "sebastian ortega"  # gana el valor nuevo, no el viejo


def test_upsert_mezcla_reemplazo_y_alta_en_la_misma_llamada():
    cached_df = api._build_and_normalize_indexed([_contact(1, "ana perdomo"), _contact(2, "uriel ortega")])
    new_df = api._build_and_normalize_indexed([_contact(1, "sebastian ortega"), _contact(3, "nueva persona")])

    result = api._upsert_contacts_df(cached_df, new_df)

    assert len(result) == 3
    assert result.loc[1, "propietario"] == "sebastian ortega"  # actualizado
    assert result.loc[2, "propietario"] == "uriel ortega"      # sin tocar
    assert result.loc[3, "propietario"] == "nueva persona"     # nuevo


# --- _load_cached_contacts: casos borde defensivos ---

def test_load_cached_contacts_sin_archivo_devuelve_none():
    assert api._load_cached_contacts() is None


def test_load_cached_contacts_archivo_corrupto_devuelve_none(tmp_path):
    api.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    api.CONTACTS_CACHE_PATH.write_bytes(b"esto no es un parquet valido")
    assert api._load_cached_contacts() is None


def test_load_cached_contacts_parquet_valido_pero_sin_indice_contact_id_devuelve_none(tmp_path):
    api.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Parquet técnicamente válido, pero con índice RangeIndex normal (no
    # `_contact_id`) -> no es la forma esperada, debe tratarse como inválido.
    pd.DataFrame({"a": [1, 2]}).to_parquet(api.CONTACTS_CACHE_PATH)
    assert api._load_cached_contacts() is None


# --- _fetch_and_build_dataframe: orquestación completa (sin red real) ---

def test_primera_vez_sin_cache_hace_full_sync_y_persiste(monkeypatch):
    calls = {"full": 0}

    def fake_full(token, base_url):
        calls["full"] += 1
        return [_contact(1, "ana perdomo"), _contact(2, "uriel ortega")]

    monkeypatch.setattr(api, "_fetch_all_contacts", fake_full)

    df = api._fetch_and_build_dataframe("fake-token", "https://api.clientify.net/v1")

    assert calls["full"] == 1
    assert len(df) == 2
    assert isinstance(df.index, pd.RangeIndex)  # el índice _contact_id NO se filtra a analytics/

    # Quedó persistido en disco para la próxima "sesión".
    assert api.CONTACTS_CACHE_PATH.exists()


def test_con_cache_existente_igual_usa_fetch_all_contacts(monkeypatch):
    # "Sesión anterior": ya hay cache en disco.
    primer_sync_contacts = [_contact(1, "ana perdomo"), _contact(2, "uriel ortega")]
    cached_df = api._build_and_normalize_indexed(primer_sync_contacts)
    api._save_contacts_cache(cached_df)

    calls = {"full": 0}

    def fake_full(token, base_url):
        calls["full"] += 1
        return [_contact(1, "ana perdomo"), _contact(2, "uriel ortega"), _contact(3, "sebastian ortega")]

    monkeypatch.setattr(api, "_fetch_all_contacts", fake_full)

    df = api._fetch_and_build_dataframe("fake-token", "https://api.clientify.net/v1")

    assert calls["full"] == 1  # SIEMPRE full sync, haya o no cache previo en disco

    # El resultado final tiene los 2 de antes + el nuevo -> upsert correcto.
    assert len(df) == 3
    assert set(df["propietario"]) == {"ana perdomo", "uriel ortega", "sebastian ortega"}


def test_sync_con_contacto_actualizado_reemplaza_no_duplica(monkeypatch):
    cached_df = api._build_and_normalize_indexed([_contact(1, "ana perdomo")])
    api._save_contacts_cache(cached_df)

    def fake_full(token, base_url):
        return [_contact(1, "sebastian ortega")]  # mismo ID, cambió de asesor

    monkeypatch.setattr(api, "_fetch_all_contacts", fake_full)

    df = api._fetch_and_build_dataframe("fake-token", "https://api.clientify.net/v1")

    assert len(df) == 1  # no duplicó
    assert df.loc[0, "propietario"] == "sebastian ortega"  # quedó el valor actualizado


def test_cache_corrupto_no_rompe_el_flujo(monkeypatch):
    api.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    api.CONTACTS_CACHE_PATH.write_bytes(b"basura, no es parquet")

    calls = {"full": 0}

    def fake_full(token, base_url):
        calls["full"] += 1
        return [_contact(1, "ana perdomo")]

    monkeypatch.setattr(api, "_fetch_all_contacts", fake_full)

    df = api._fetch_and_build_dataframe("fake-token", "https://api.clientify.net/v1")

    assert calls["full"] == 1  # cache inválido -> igual sincroniza, no explota
    assert len(df) == 1


def test_cache_vacio_en_disco_no_rompe_el_flujo(monkeypatch):
    """Caso borde explícito pedido: el archivo de cache EXISTE pero
    representa un DataFrame vacío (0 filas) — distinto de "corrupto" (no
    legible) pero igual de inútil para un upsert con sentido."""
    empty_df = api._build_and_normalize_indexed([])
    api._save_contacts_cache(empty_df)

    calls = {"full": 0}
    monkeypatch.setattr(
        api, "_fetch_all_contacts",
        lambda *a, **k: calls.__setitem__("full", calls["full"] + 1) or [_contact(1, "ana perdomo")],
    )

    df = api._fetch_and_build_dataframe("fake-token", "https://api.clientify.net/v1")

    assert calls["full"] == 1
    assert len(df) == 1


def test_round_trip_disco_sobrevive_a_reinicio_simulado(monkeypatch):
    """Simula 2 sesiones distintas de la app: la 2da debe leer lo que la
    1ra dejó en disco y fusionarlo con lo que trae el nuevo full sync."""
    def fake_full_sesion_1(token, base_url):
        return [_contact(1, "ana perdomo"), _contact(2, "uriel ortega")]

    monkeypatch.setattr(api, "_fetch_all_contacts", fake_full_sesion_1)

    df_sesion_1 = api._fetch_and_build_dataframe("fake-token", "https://api.clientify.net/v1")
    assert len(df_sesion_1) == 2

    # "Reinicio de la app": el único estado que sobrevive es lo que quedó en
    # disco (no hay nada en memoria de Python que reutilizar acá). El nuevo
    # full sync trae los mismos 2 + 1 contacto nuevo.
    def fake_full_sesion_2(token, base_url):
        return [_contact(1, "ana perdomo"), _contact(2, "uriel ortega"), _contact(3, "sebastian ortega")]

    monkeypatch.setattr(api, "_fetch_all_contacts", fake_full_sesion_2)

    df_sesion_2 = api._fetch_and_build_dataframe("fake-token", "https://api.clientify.net/v1")

    assert len(df_sesion_2) == 3
    assert set(df_sesion_2["propietario"]) == {"ana perdomo", "uriel ortega", "sebastian ortega"}
