"""Tests de la paginación PARALELIZADA de `_fetch_all_contacts`
(src/data_sources/clientify_api.py).

Contexto: confirmado empíricamente contra la cuenta real (ver
`MAX_PARALLEL_WORKERS` en clientify_api.py) que esta API tolera 10 requests
simultáneas a `/contacts/?page=N` sin 429 ni degradación — por eso
`_fetch_all_contacts` pasó de paginar secuencialmente (siguiendo `next`) a
pedir la página 1 sola (para conocer `count`) y el resto en paralelo con
`ThreadPoolExecutor`, reconstruyendo el orden final por número de página
(no por orden de llegada) y reintentando páginas puntuales que fallen.
"""
import requests

from src.data_sources import clientify_api as api


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    """Simula `requests.Session.get` contra `/contacts/?page=N&page_size=M`.

    `pages`: dict page -> lista de contactos de esa página.
    `count`: total reportado en la respuesta de CUALQUIER página (la API
    real lo repite en todas, no solo en la primera).
    `fail_on_page`: si se da, la PRIMERA vez que se pide esa página lanza una
    excepción de red — la 2da vez (reintento) responde normal. Simula un
    blip transitorio en una sola página sin afectar al resto del sync.
    `always_fail_page`: si se da, esa página SIEMPRE falla (agota reintentos).
    """

    def __init__(self, pages, count, fail_on_page=None, always_fail_page=None):
        self.pages = pages
        self.count = count
        self.fail_on_page = fail_on_page
        self.always_fail_page = always_fail_page
        self._already_failed_once = set()
        self.calls: list[int] = []

    def get(self, url, params=None, timeout=None):
        page = params["page"]
        self.calls.append(page)
        if self.always_fail_page == page:
            raise requests.exceptions.ConnectionError(f"falla simulada permanente en página {page}")
        if self.fail_on_page == page and page not in self._already_failed_once:
            self._already_failed_once.add(page)
            raise requests.exceptions.ConnectionError(f"blip de red simulado en página {page}")
        return _FakeResponse({"results": self.pages.get(page, []), "count": self.count})


def _patch_session(monkeypatch, fake_session):
    monkeypatch.setattr(api, "_build_session", lambda token: fake_session)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)  # no esperar el backoff real en tests


def test_todo_cabe_en_la_pagina_1_no_dispara_workers_extra(monkeypatch):
    fake_session = _FakeSession(pages={1: [{"id": 1}, {"id": 2}]}, count=2)
    _patch_session(monkeypatch, fake_session)

    contacts = api._fetch_all_contacts("fake-token", "https://api.clientify.net/v1")

    assert [c["id"] for c in contacts] == [1, 2]
    assert fake_session.calls == [1]  # una sola llamada, nada en paralelo


def test_pagina_todas_las_paginas_sin_duplicados_ni_faltantes(monkeypatch):
    # count=7, page_size real=2 (deducido del tamaño de la página 1) -> 4 páginas
    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}, {"id": 4}],
        3: [{"id": 5}, {"id": 6}],
        4: [{"id": 7}],
    }
    fake_session = _FakeSession(pages=pages, count=7)
    _patch_session(monkeypatch, fake_session)

    contacts = api._fetch_all_contacts("fake-token", "https://api.clientify.net/v1", max_workers=4)

    ids = [c["id"] for c in contacts]
    assert sorted(ids) == [1, 2, 3, 4, 5, 6, 7]
    assert len(ids) == len(set(ids))  # sin duplicados
    assert sorted(fake_session.calls) == [1, 2, 3, 4]


def test_resultado_final_queda_ordenado_por_pagina_sin_importar_orden_de_llegada(monkeypatch):
    """Las páginas más ALTAS responden primero a propósito (orden de
    finalización invertido respecto al orden de página) — el resultado
    final debe seguir en orden 1,2,3,... porque `_fetch_all_contacts`
    reconstruye por número de página, no por orden de llegada."""
    import time as real_time

    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}, {"id": 4}],
        3: [{"id": 5}, {"id": 6}],
        4: [{"id": 7}, {"id": 8}],
    }

    class _ReversedDelaySession(_FakeSession):
        def get(self, url, params=None, timeout=None):
            page = params["page"]
            if page > 1:
                # página 2 tarda más, página 4 responde casi de inmediato
                real_time.sleep(0.01 * (5 - page))
            return super().get(url, params=params, timeout=timeout)

    fake_session = _ReversedDelaySession(pages=pages, count=8)
    monkeypatch.setattr(api, "_build_session", lambda token: fake_session)

    contacts = api._fetch_all_contacts("fake-token", "https://api.clientify.net/v1", max_workers=4)

    assert [c["id"] for c in contacts] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_pagina_con_falla_transitoria_se_reintenta_sin_tumbar_el_sync(monkeypatch):
    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}, {"id": 4}],
        3: [{"id": 5}, {"id": 6}],
    }
    fake_session = _FakeSession(pages=pages, count=6, fail_on_page=2)
    _patch_session(monkeypatch, fake_session)

    contacts = api._fetch_all_contacts("fake-token", "https://api.clientify.net/v1", max_workers=3)

    ids = sorted(c["id"] for c in contacts)
    assert ids == [1, 2, 3, 4, 5, 6]  # la página 2 se recuperó, no se perdió nada
    assert fake_session.calls.count(2) == 2  # 1 falla + 1 reintento exitoso


def test_pagina_que_agota_reintentos_propaga_la_excepcion(monkeypatch):
    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}, {"id": 4}],
    }
    fake_session = _FakeSession(pages=pages, count=4, always_fail_page=2)
    _patch_session(monkeypatch, fake_session)

    try:
        api._fetch_all_contacts("fake-token", "https://api.clientify.net/v1", max_workers=2)
        assert False, "debería haber propagado la excepción de la página 2"
    except requests.exceptions.ConnectionError:
        pass

    assert fake_session.calls.count(2) == 3  # 3 intentos (retries=3 por defecto), todos fallidos


def test_fetch_page_reintenta_y_se_recupera(monkeypatch):
    fake_session = _FakeSession(pages={1: [{"id": 1}]}, count=1, fail_on_page=1)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)

    payload = api._fetch_page(fake_session, "https://api.clientify.net/v1", page=1)

    assert payload["results"] == [{"id": 1}]
    assert fake_session.calls.count(1) == 2
