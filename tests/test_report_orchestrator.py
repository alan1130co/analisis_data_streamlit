"""Tests de `src/reports/report_orchestrator.py` — una llamada de IA por
grupo + 1 de resumen ejecutivo, y si una llamada de grupo falla, el reporte
sigue generándose igual con una nota "Análisis no disponible" en esa
sección (nunca se aborta todo). Todo con un `AIProvider` falso — sin red.
"""
from src.analytics.report_payload import GRUPOS_ORDEN, GRUPOS_TITULOS
from src.data_sources.ai_provider import AIProvider, AIProviderError
from src.reports.report_orchestrator import (
    ANALISIS_NO_DISPONIBLE,
    generate_full_report_analysis,
    payload_hash,
)


def _es_nota_no_disponible(texto: str, motivo: str) -> bool:
    """La nota de "no disponible" ya no es un texto genérico fijo (ver
    `ANALISIS_NO_DISPONIBLE`) — ahora incluye el motivo sanitizado de la
    falla real (saldo insuficiente, timeout, etc., ver
    `AIProviderError`/`_nota_no_disponible`), para que el reporte y la UI
    nunca muestren un "no disponible" sin ninguna pista de qué pasó."""
    return "Análisis no disponible" in texto and motivo in texto


class _FakeProvider(AIProvider):
    """`fallar_en`: conjunto de prompts de usuario que deben lanzar
    `AIProviderError` (simula que esa llamada específica falló)."""

    def __init__(self, fallar_en_grupo: str | None = None):
        self._fallar_en_grupo = fallar_en_grupo
        self.llamadas: list[tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.llamadas.append((system_prompt, user_prompt))
        if self._fallar_en_grupo and self._fallar_en_grupo in system_prompt:
            raise AIProviderError("simulado: la API no respondió")
        return f"Análisis OK para: {system_prompt[:30]}"


def _payload_minimo() -> dict:
    return {
        "periodo": "Todos",
        "grupos": {gid: {"placeholder": {"promedio": 1.0}} for gid in GRUPOS_ORDEN},
    }


def test_una_llamada_por_grupo_mas_resumen_ejecutivo():
    provider = _FakeProvider()
    resultado = generate_full_report_analysis(provider, _payload_minimo())
    # 5 grupos + 1 resumen ejecutivo = 6 llamadas totales.
    assert len(provider.llamadas) == len(GRUPOS_ORDEN) + 1
    assert set(resultado["grupos"].keys()) == set(GRUPOS_ORDEN)
    assert "resumen_ejecutivo" in resultado


def test_grupo_fallido_queda_con_nota_no_disponible_sin_abortar_el_resto():
    titulo_que_falla = GRUPOS_TITULOS["costo_por_lead"]
    provider = _FakeProvider(fallar_en_grupo=titulo_que_falla)
    resultado = generate_full_report_analysis(provider, _payload_minimo())

    # La nota incluye el motivo real sanitizado (no un texto genérico sin
    # pistas) — ver `_es_nota_no_disponible`.
    assert _es_nota_no_disponible(resultado["grupos"]["costo_por_lead"], "simulado: la API no respondió")
    # El resto de los grupos SÍ se generó con éxito (el reporte sigue
    # completo salvo esa sección).
    for gid in GRUPOS_ORDEN:
        if gid == "costo_por_lead":
            continue
        assert "Análisis no disponible" not in resultado["grupos"][gid]
        assert resultado["grupos"][gid].startswith("Análisis OK")
    # El resumen ejecutivo también se generó (no se abortó el reporte).
    assert resultado["resumen_ejecutivo"].startswith("Análisis OK")


def test_resumen_ejecutivo_tambien_falla_queda_con_nota():
    # Confirmamos que un AIProviderError en la llamada del resumen
    # ejecutivo también degrada con la misma nota (no rompe el reporte),
    # usando un provider que siempre falla.
    class _SiempreFalla(AIProvider):
        def generate(self, system_prompt, user_prompt):
            raise AIProviderError("todo falla")

    resultado = generate_full_report_analysis(_SiempreFalla(), _payload_minimo())
    assert _es_nota_no_disponible(resultado["resumen_ejecutivo"], "todo falla")
    for gid in GRUPOS_ORDEN:
        assert _es_nota_no_disponible(resultado["grupos"][gid], "todo falla")


def test_on_progress_se_llama_una_vez_por_grupo_mas_resumen():
    provider = _FakeProvider()
    llamadas_progreso = []

    def _on_progress(indice, total, descripcion):
        llamadas_progreso.append((indice, total, descripcion))

    generate_full_report_analysis(provider, _payload_minimo(), on_progress=_on_progress)

    total_esperado = len(GRUPOS_ORDEN) + 1
    assert len(llamadas_progreso) == total_esperado
    assert [c[0] for c in llamadas_progreso] == list(range(1, total_esperado + 1))
    assert all(c[1] == total_esperado for c in llamadas_progreso)
    # La última llamada de progreso es la del resumen ejecutivo.
    assert llamadas_progreso[-1][2] == "Resumen ejecutivo"


def test_payload_hash_estable_para_el_mismo_payload():
    payload = _payload_minimo()
    assert payload_hash(payload) == payload_hash(_payload_minimo())


def test_payload_hash_cambia_si_el_payload_cambia():
    payload_a = _payload_minimo()
    payload_b = _payload_minimo()
    payload_b["grupos"]["costo_por_lead"]["placeholder"]["promedio"] = 999.0
    assert payload_hash(payload_a) != payload_hash(payload_b)
