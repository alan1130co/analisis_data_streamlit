"""Tests de `src/analytics/report_payload.py` — verifica que el payload
armado para el análisis de IA (1) nunca contiene PII ni filas crudas de
Clientify, solo agregados mensuales, y (2) que esos agregados (promedio,
mejor/peor mes, variación % mes a mes, tendencia) coinciden con el cálculo
manual sobre los mismos datos."""
import json

import pandas as pd

from src.analytics.report_payload import (
    GRUPOS_ORDEN,
    PERIODO_TODOS,
    build_report_payload,
)

# --- Valores "PII" de referencia: no deben aparecer en ningún punto del
# payload serializado (ni como clave ni como valor) ---
_PII_NOMBRE = "Maria Fernanda Rodriguez Lopez"
_PII_EMAIL = "maria.fernanda.rodriguez@example.com"
_PII_TELEFONO = "+57 300 1234567"


def _gasto_raw() -> pd.DataFrame:
    return pd.DataFrame([
        {"Fecha": "01/01/2025", "Divisa": "USD", "Importe": "1000"},
        {"Fecha": "01/02/2025", "Divisa": "USD", "Importe": "2000"},
        {"Fecha": "01/01/2026", "Divisa": "USD", "Importe": "3000"},
    ])


def _billed_raw() -> pd.DataFrame:
    return pd.DataFrame([
        {"Fecha": "01/01/2025", "Divisa": "USD", "Importe": "900"},
        {"Fecha": "01/02/2025", "Divisa": "USD", "Importe": "1800"},
    ])


def _df_clientify() -> pd.DataFrame:
    """Incluye columnas de PII real (nombre/email/teléfono) junto con las
    columnas de negocio que sí necesitan `ad_spend_vs_closures.py` — el
    payload debe construirse SOLO a partir de las segundas."""
    rows = []
    # 2 cierres de redes en Enero 2025, 1 en Enero 2026 — valores elegidos
    # para poder verificar promedio/mejor/peor mes a mano.
    datos = [
        ("01/01/2025", 500, 5000),
        ("15/01/2025", 300, 3000),
        ("01/01/2026", 1200, 8000),
    ]
    for fecha_cierre, cuota_inicial, valor_proceso in datos:
        rows.append({
            "nombre": _PII_NOMBRE,
            "email": _PII_EMAIL,
            "telefono": _PII_TELEFONO,
            "estado": "activo",
            "Canal offline": "Clientify - Facebook",
            "canal online": "paid social",
            "Fecha de cierre": fecha_cierre,
            "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None,
            "Fecha de 4to cierre": None,
            "Cuota inicial pactada": str(cuota_inicial),
            "Valor total del proceso": str(valor_proceso),
        })
    return pd.DataFrame(rows)


def test_payload_sin_pii():
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    serializado = json.dumps(payload, ensure_ascii=False, default=str)
    assert _PII_NOMBRE not in serializado
    assert _PII_EMAIL not in serializado
    assert _PII_TELEFONO not in serializado
    assert "nombre" not in serializado
    assert "email" not in serializado
    assert "telefono" not in serializado


def test_payload_sin_pii_columnas_clientify_crudas():
    """Ninguna columna cruda de `df_clientify` (ni de negocio ni PII) debe
    aparecer como clave en el payload — solo las claves agregadas que
    arma `_series_stats` ('serie_mensual', 'promedio', etc.)."""
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    serializado = json.dumps(payload, ensure_ascii=False, default=str)
    for columna_cruda in ["Canal offline", "canal online", "Cuota inicial pactada", "Valor total del proceso"]:
        assert columna_cruda not in serializado


def test_payload_tiene_los_5_grupos():
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    assert payload["periodo"] == PERIODO_TODOS
    assert set(payload["grupos"].keys()) == set(GRUPOS_ORDEN)
    assert len(GRUPOS_ORDEN) == 5


def test_promedio_gasto_pauta_correcto():
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    gasto_stats = payload["grupos"]["costo_por_lead"]["gasto_pauta"]
    # 1000 + 2000 + 3000 = 6000 / 3 meses = 2000.0
    assert gasto_stats["promedio"] == 2000.0


def test_mejor_y_peor_mes_correctos():
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    gasto_stats = payload["grupos"]["costo_por_lead"]["gasto_pauta"]
    assert gasto_stats["mejor_mes"] == {"mes": "Enero 2026", "valor": 3000.0}
    assert gasto_stats["peor_mes"] == {"mes": "Enero 2025", "valor": 1000.0}


def test_variacion_mensual_pct_correcta():
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    gasto_stats = payload["grupos"]["costo_por_lead"]["gasto_pauta"]
    variaciones = {v["mes"]: v["variacion_pct"] for v in gasto_stats["variacion_mensual_pct"]}
    # Enero 2025 (1000) -> Febrero 2025 (2000): +100%
    assert variaciones["Febrero 2025"] == 100.0


def test_diferencia_real_vs_facturado_total():
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    grupo = payload["grupos"]["gasto_y_facturado"]
    # Real: 1000+2000(+3000 sin facturar) = 6000 ; Facturado: 900+1800 = 2700
    # Diferencia = 6000 - 2700 = 3300
    assert grupo["diferencia_real_vs_facturado_total"] == 3300.0


def test_filtro_por_anio_excluye_otros_anios():
    payload_2025 = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=2025)
    gasto_stats = payload_2025["grupos"]["costo_por_lead"]["gasto_pauta"]
    meses = {p["mes"] for p in gasto_stats["serie_mensual"]}
    assert meses == {"Enero 2025", "Febrero 2025"}
    assert "Enero 2026" not in meses


def test_periodo_todos_incluye_todos_los_anios():
    payload = build_report_payload(_gasto_raw(), _df_clientify(), _billed_raw(), anio=PERIODO_TODOS)
    gasto_stats = payload["grupos"]["costo_por_lead"]["gasto_pauta"]
    meses = {p["mes"] for p in gasto_stats["serie_mensual"]}
    assert meses == {"Enero 2025", "Febrero 2025", "Enero 2026"}


def test_sin_datos_devuelve_tendencia_sin_datos():
    payload = build_report_payload(pd.DataFrame(), pd.DataFrame(), None, anio=PERIODO_TODOS)
    for grupo in payload["grupos"].values():
        for metrica in grupo.values():
            if isinstance(metrica, dict) and "tendencia" in metrica:
                assert metrica["tendencia"] == "sin_datos"
                assert metrica["serie_mensual"] == []
