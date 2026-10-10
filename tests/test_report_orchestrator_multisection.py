"""Tests de la generalización multi-sección de `report_orchestrator.py`:
- `generate_section_analysis` funciona para CUALQUIER sección (no solo
  Marketing), con las mismas garantías de "nunca aborta" que ya cubre
  `tests/test_report_orchestrator.py` para Marketing.
- `generate_combined_report_analysis` ("reporte completo"): corre todas las
  secciones disponibles, omite las que falten, y el ORDEN del resultado
  respeta `SECTIONS_ORDEN` aunque las llamadas (en paralelo) terminen en
  otro orden.
- Las llamadas corren en paralelo (más rápido que la suma secuencial) y el
  progreso siempre avanza en orden creciente 1..N.

Todo con un `AIProvider` falso — sin red.
"""
import time

from src.data_sources.ai_provider import AIProvider, AIProviderError
from src.reports.report_orchestrator import (
    generate_combined_report_analysis,
    generate_section_analysis,
)
from src.reports.section_registry import SECTIONS, SECTIONS_ORDEN


class _FakeProviderConDelay(AIProvider):
    """Cada grupo tarda un tiempo DISTINTO (el primero en recibirse es el
    que más tarda) — para forzar que las llamadas NO terminen en el mismo
    orden en que se mandaron, y así probar que el reensamblado final
    respeta el orden lógico (de sección/grupo), no el de finalización."""

    def __init__(self):
        self.llamadas: list[str] = []
        self._contador = 0

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self._contador += 1
        # El primer grupo en pedirse duerme más — termina último.
        time.sleep(0.03 if self._contador == 1 else 0.001)
        self.llamadas.append(system_prompt[:40])
        return f"Análisis OK #{self._contador}"


class _FakeProviderFallaUnGrupo(AIProvider):
    def __init__(self, texto_que_falla: str):
        self._texto_que_falla = texto_que_falla

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self._texto_que_falla in system_prompt:
            raise AIProviderError("simulado: falla puntual")
        return "Análisis OK"


def _payload_minimo(section_id: str) -> dict:
    spec = SECTIONS[section_id]
    return {"periodo": "2026-01", "grupos": {g.id: {"placeholder": {"promedio": 1.0}} for g in spec.groups}}


class TestGenerateSectionAnalysisGenerico:
    def test_funciona_para_segmentacion_no_solo_marketing(self):
        provider = _FakeProviderConDelay()
        resultado = generate_section_analysis(provider, SECTIONS["segmentacion"], _payload_minimo("segmentacion"))
        assert set(resultado["grupos"].keys()) == set(SECTIONS["segmentacion"].group_ids)
        assert "resumen_ejecutivo" in resultado
        assert "costo_real_usd" in resultado

    def test_fallo_de_un_grupo_no_aborta_las_demas_secciones_nuevas(self):
        spec = SECTIONS["embudo"]
        titulo_que_falla = spec.groups[0].title
        provider = _FakeProviderFallaUnGrupo(titulo_que_falla)
        resultado = generate_section_analysis(provider, spec, _payload_minimo("embudo"))

        assert "Análisis no disponible" in resultado["grupos"][spec.groups[0].id]
        for g in spec.groups[1:]:
            assert resultado["grupos"][g.id] == "Análisis OK"
        assert resultado["resumen_ejecutivo"] == "Análisis OK"


class TestGenerateCombinedReportAnalysis:
    def test_todas_las_secciones_disponibles_en_el_orden_logico(self):
        provider = _FakeProviderConDelay()
        payloads = {sid: _payload_minimo(sid) for sid in SECTIONS_ORDEN}

        resultado = generate_combined_report_analysis(provider, payloads)

        assert resultado["secciones_incluidas"] == SECTIONS_ORDEN
        assert resultado["secciones_omitidas"] == []
        for sid in SECTIONS_ORDEN:
            assert set(resultado["analisis_por_seccion"][sid].keys()) == set(SECTIONS[sid].group_ids)

    def test_secciones_sin_datos_se_omiten_sin_romper_el_resto(self):
        provider = _FakeProviderConDelay()
        # Solo 2 de las 4 secciones tienen payload (simula "sin datos" en las otras).
        payloads = {"marketing": _payload_minimo("marketing"), "gestion_comercial": _payload_minimo("gestion_comercial")}

        resultado = generate_combined_report_analysis(provider, payloads)

        assert resultado["secciones_incluidas"] == ["marketing", "gestion_comercial"]
        assert set(resultado["secciones_omitidas"]) == {"segmentacion", "embudo"}
        assert "marketing" in resultado["analisis_por_seccion"]
        assert "gestion_comercial" in resultado["analisis_por_seccion"]

    def test_fallo_de_un_grupo_de_una_seccion_no_aborta_el_reporte_completo(self):
        titulo_que_falla = SECTIONS["marketing"].groups[0].title
        provider = _FakeProviderFallaUnGrupo(f"[{SECTIONS['marketing'].title}] {titulo_que_falla}")
        payloads = {sid: _payload_minimo(sid) for sid in SECTIONS_ORDEN}

        resultado = generate_combined_report_analysis(provider, payloads)

        grupo_fallido_id = SECTIONS["marketing"].groups[0].id
        assert "Análisis no disponible" in resultado["analisis_por_seccion"]["marketing"][grupo_fallido_id]
        # El resto de los grupos de Marketing y las otras 3 secciones sí se generaron.
        otros_grupos_marketing = [g.id for g in SECTIONS["marketing"].groups[1:]]
        for gid in otros_grupos_marketing:
            assert resultado["analisis_por_seccion"]["marketing"][gid] == "Análisis OK"
        for sid in ("segmentacion", "embudo", "gestion_comercial"):
            for g in SECTIONS[sid].groups:
                assert resultado["analisis_por_seccion"][sid][g.id] == "Análisis OK"
        # El resumen ejecutivo global también se generó (no se abortó el reporte).
        assert resultado["resumen_ejecutivo_global"] == "Análisis OK"

    def test_progreso_siempre_en_orden_creciente_pese_a_correr_en_paralelo(self):
        provider = _FakeProviderConDelay()
        payloads = {sid: _payload_minimo(sid) for sid in SECTIONS_ORDEN}
        llamadas_progreso: list[tuple[int, int, str]] = []

        def _on_progress(indice, total, descripcion):
            llamadas_progreso.append((indice, total, descripcion))

        generate_combined_report_analysis(provider, payloads, on_progress=_on_progress)

        total_grupos = sum(len(SECTIONS[sid].groups) for sid in SECTIONS_ORDEN) + 1
        assert [c[0] for c in llamadas_progreso] == list(range(1, total_grupos + 1))
        assert all(c[1] == total_grupos for c in llamadas_progreso)
        assert llamadas_progreso[-1][2] == "Resumen ejecutivo global"

    def test_corre_en_paralelo_mas_rapido_que_secuencial(self):
        """Con MAX_WORKERS=4 y 4+ grupos de ~10ms cada uno, el total debe
        ser notablemente menor que la suma secuencial — prueba indirecta
        de que SÍ corren en paralelo, no uno por uno."""
        class _ProviderLento(AIProvider):
            def generate(self, system_prompt: str, user_prompt: str) -> str:
                time.sleep(0.05)
                return "ok"

        payloads = {sid: _payload_minimo(sid) for sid in SECTIONS_ORDEN}
        total_grupos = sum(len(SECTIONS[sid].groups) for sid in SECTIONS_ORDEN)

        inicio = time.perf_counter()
        generate_combined_report_analysis(_ProviderLento(), payloads, max_workers=4)
        duracion = time.perf_counter() - inicio

        duracion_secuencial_estimada = (total_grupos + 1) * 0.05
        assert duracion < duracion_secuencial_estimada * 0.8
