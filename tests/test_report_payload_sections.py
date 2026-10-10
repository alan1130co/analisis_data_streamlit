"""Tests "sin PII" + estructura de los payloads de las 3 secciones NUEVAS
del reporte de IA (Segmentación Clave, Embudo y Canales, Gestión Comercial)
— mismo criterio que `tests/test_report_payload.py` (Marketing): el
payload NUNCA debe contener PII de un CLIENTE/lead de Clientify (nombre,
email, teléfono) ni filas crudas, solo agregados por categoría/período.

El nombre de un ASESOR (propietario, columna distinta de "nombre" del
cliente) SÍ puede aparecer en el grupo "embudo_por_asesor" — es personal
interno, no un contacto de Clientify, y el propio inventario de la tarea
lo señaló así explícitamente.
"""
import json

import pandas as pd

from src.analytics.metrics import compute_all_metrics
from src.analytics.report_payload_embudo import GRUPOS_ORDEN as EMBUDO_GRUPOS_ORDEN
from src.analytics.report_payload_embudo import build_report_payload as build_embudo_payload
from src.analytics.report_payload_gestion_comercial import GRUPOS_ORDEN as GESTION_GRUPOS_ORDEN
from src.analytics.report_payload_gestion_comercial import build_report_payload as build_gestion_payload
from src.analytics.report_payload_segmentacion import GRUPOS_ORDEN as SEGMENTACION_GRUPOS_ORDEN
from src.analytics.report_payload_segmentacion import build_report_payload as build_segmentacion_payload

_PII_NOMBRE = "Maria Fernanda Rodriguez Lopez"
_PII_EMAIL = "maria.fernanda.rodriguez@example.com"
_PII_TELEFONO = "+57 300 1234567"

_ASESOR_PLANTA = "Ana Perdomo"


def _df_clientify() -> pd.DataFrame:
    rows = []
    datos = [
        ("01/01/2026", "15/01/2026", "colombia", "atlantico", "barranquilla", "salud", "visa", 28),
        ("01/01/2026", "20/01/2026", "colombia", "bogota dc", "bogota", "educacion", "ciudadania", 45),
        ("05/01/2026", "25/01/2026", "mexico", "jalisco", "guadalajara", "salud", "visa", 60),
    ]
    for fecha_creado, fecha_cierre, pais, estado, ciudad, sector, tipo_proceso, edad in datos:
        rows.append({
            "nombre": _PII_NOMBRE,
            "email": _PII_EMAIL,
            "telefono": _PII_TELEFONO,
            "creado": fecha_creado,
            "estado": "activo",
            "propietario": _ASESOR_PLANTA,
            "Canal offline": "Clientify - Facebook",
            "Origen de la pauta": "Facebook",
            "canal online": "paid social",
            "país": pais,
            "provincia/estado 1": estado,
            "ciudad 1": ciudad,
            "sector": sector,
            "Tipo de proceso": tipo_proceso,
            "cumpleaños": f"01/01/{2026 - edad}",
            "Campaña - pauta": "Campana Enero",
            "Publicacion por la que se contacto el cliente": "Video promo",
            "Motivo de no cierre": "",
            "Fecha de cierre": fecha_cierre,
            "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None,
            "Fecha de 4to cierre": None,
            "Cuota inicial pactada": "500",
            "Valor total del proceso": "5000",
        })
    return pd.DataFrame(rows)


def _assert_sin_pii_de_cliente(payload: dict) -> None:
    serializado = json.dumps(payload, ensure_ascii=False, default=str)
    assert _PII_NOMBRE not in serializado
    assert _PII_EMAIL not in serializado
    assert _PII_TELEFONO not in serializado
    assert "email" not in serializado
    assert "telefono" not in serializado


class TestSegmentacionPayload:
    def test_sin_pii(self):
        payload = build_segmentacion_payload(_df_clientify(), 2026, 1, team="Todos")
        _assert_sin_pii_de_cliente(payload)

    def test_tiene_los_3_grupos(self):
        payload = build_segmentacion_payload(_df_clientify(), 2026, 1, team="Todos")
        assert set(payload["grupos"].keys()) == set(SEGMENTACION_GRUPOS_ORDEN)
        assert len(SEGMENTACION_GRUPOS_ORDEN) == 3

    def test_geografia_tiene_categorias_agregadas(self):
        payload = build_segmentacion_payload(_df_clientify(), 2026, 1, team="Todos")
        pais = payload["grupos"]["geografia_cierres"]["pais"]
        assert pais["total"] == 3
        assert pais["categoria_lider"]["categoria"] in {"colombia", "mexico"}

    def test_perfil_cliente_incluye_nota_genero(self):
        payload = build_segmentacion_payload(_df_clientify(), 2026, 1, team="Todos")
        assert "SUPUESTO" in payload["grupos"]["perfil_cliente"]["nota_genero"]

    def test_sin_datos_devuelve_estructura_vacia(self):
        payload = build_segmentacion_payload(pd.DataFrame(), 2026, 1)
        for grupo in payload["grupos"].values():
            for metrica in grupo.values():
                if isinstance(metrica, dict) and "total" in metrica:
                    assert metrica["total"] == 0


class TestEmbudoPayload:
    def test_sin_pii(self):
        payload = build_embudo_payload(_df_clientify(), 2026, 1, team="Todos")
        _assert_sin_pii_de_cliente(payload)

    def test_tiene_los_4_grupos(self):
        payload = build_embudo_payload(_df_clientify(), 2026, 1, team="Todos")
        assert set(payload["grupos"].keys()) == set(EMBUDO_GRUPOS_ORDEN)
        assert len(EMBUDO_GRUPOS_ORDEN) == 4

    def test_embudo_por_asesor_incluye_nombre_de_asesor_no_es_pii_de_cliente(self):
        """El nombre de ASESOR (personal interno) puede aparecer — no es un
        dato de contacto de un cliente/lead de Clientify."""
        payload = build_embudo_payload(_df_clientify(), 2026, 1, team="Todos")
        asesores = payload["grupos"]["embudo_por_asesor"]["asesores"]
        nombres = {fila["Asesor"] for fila in asesores}
        assert _ASESOR_PLANTA.title() in nombres

    def test_pauta_vs_referidos_nunca_usa_el_detalle_con_nombre_de_cliente(self):
        """El grupo debe usar SOLO el agregado Origen×Cohorte — nunca la
        tabla fila-por-fila que expone "Cliente" (nombre real)."""
        payload = build_embudo_payload(_df_clientify(), 2026, 1, team="Todos")
        grupo = payload["grupos"]["pauta_vs_referidos"]
        assert "Cliente" not in json.dumps(grupo, ensure_ascii=False, default=str)
        assert set(grupo.keys()) == {"pauta_vs_referidos", "por_antiguedad_cohorte"}
        for fila in grupo["por_antiguedad_cohorte"]:
            assert set(fila.keys()) == {"Cohorte", "Origen", "Cantidad"}

    def test_evolucion_temporal_agrega_por_canal(self):
        payload = build_embudo_payload(_df_clientify(), 2026, 1, team="Todos")
        series = payload["grupos"]["evolucion_temporal"]["series_por_canal"]
        assert isinstance(series, dict)


class TestGestionComercialPayload:
    def test_sin_pii(self):
        df = _df_clientify()
        metrics = compute_all_metrics(df, df)
        payload = build_gestion_payload(df, 2026, 1, metrics=metrics, metrics_prev=metrics)
        _assert_sin_pii_de_cliente(payload)

    def test_tiene_los_4_grupos(self):
        df = _df_clientify()
        metrics = compute_all_metrics(df, df)
        payload = build_gestion_payload(df, 2026, 1, metrics=metrics, metrics_prev=metrics)
        assert set(payload["grupos"].keys()) == set(GESTION_GRUPOS_ORDEN)
        assert len(GESTION_GRUPOS_ORDEN) == 4

    def test_kpis_del_mes_sin_metrics_da_nota_insuficiente(self):
        payload = build_gestion_payload(_df_clientify(), 2026, 1, metrics=None, metrics_prev=None)
        assert payload["grupos"]["kpis_del_mes"]["kpis"] == {}
        assert "dato insuficiente" in payload["grupos"]["kpis_del_mes"]["nota"]

    def test_motivos_no_cierre_agregado_por_categoria(self):
        df = _df_clientify()
        metrics = compute_all_metrics(df, df)
        payload = build_gestion_payload(df, 2026, 1, metrics=metrics, metrics_prev=metrics)
        assert "motivos" in payload["grupos"]["motivos_no_cierre"]
