"""Tests para Cierres por canal (Pauta directa vs Referidos) en el tiempo."""
from datetime import datetime

import pandas as pd

from src.analytics.closures_by_channel_over_time import closures_by_channel_over_time


def _lead(canal_offline, fecha_cierre=pd.NaT, fecha_segundo=pd.NaT, fecha_tercer=pd.NaT, fecha_cuarto=pd.NaT):
    return {
        "Canal offline": canal_offline,
        "Fecha de cierre": fecha_cierre,
        "Fecha de segundo cierre": fecha_segundo,
        "Fecha de tercer cierre": fecha_tercer,
        "Fecha de 4to cierre": fecha_cuarto,
    }


def test_clasifica_pauta_directa_vs_referido():
    df = pd.DataFrame([
        _lead("clientify - facebook", fecha_cierre=datetime(2026, 4, 5)),
        _lead("referido externo", fecha_cierre=datetime(2026, 4, 6)),
    ])
    out = closures_by_channel_over_time(df)
    pauta_row = out[(out["Canal"] == "Pauta directa") & (out["Año-Mes"] == "2026-04")]
    referido_row = out[(out["Canal"] == "Referido") & (out["Año-Mes"] == "2026-04")]
    assert pauta_row["Total cierres"].iloc[0] == 1
    assert referido_row["Total cierres"].iloc[0] == 1


def test_clasificacion_es_insensible_a_mayusculas():
    """Canal offline viene normalizado en minúsculas por el loader real, pero
    la lista de referencia está en Title Case — debe matchear igual."""
    df = pd.DataFrame([
        _lead("tiktok", fecha_cierre=datetime(2026, 4, 1)),
        _lead("TIKTOK", fecha_cierre=datetime(2026, 4, 2)),
    ])
    out = closures_by_channel_over_time(df)
    pauta_row = out[out["Canal"] == "Pauta directa"]
    assert pauta_row["Total cierres"].iloc[0] == 2


def test_referido_redes_cuenta_como_pauta_directa():
    """'Referido cliente activo - Redes' está agregado explícitamente en
    `redes_channel_mask` (2026-08-13c) — un referido puntual que el negocio
    igual cuenta como "redes" para el conteo de cierres, aunque no matchee
    `MARKETING_OFFLINE_CHANNELS` ni Orgánico/TikTok."""
    df = pd.DataFrame([
        _lead("referido cliente activo - redes", fecha_cierre=datetime(2026, 4, 1)),
    ])
    out = closures_by_channel_over_time(df)
    assert out.iloc[0]["Canal"] == "Pauta directa"


def test_organico_cuenta_como_pauta_directa():
    """Regresión: el whitelist anterior no incluía Orgánico en absoluto —
    la nueva definición unificada (`redes_channel_mask`) sí debe contarlo."""
    df = pd.DataFrame([
        _lead("organico", fecha_cierre=datetime(2026, 4, 1)),
    ])
    out = closures_by_channel_over_time(df)
    assert out.iloc[0]["Canal"] == "Pauta directa"


def test_separa_primer_y_segundo_cierre():
    df = pd.DataFrame([
        _lead("clientify - whatsapp", fecha_cierre=datetime(2026, 5, 1), fecha_segundo=datetime(2026, 5, 20)),
    ])
    out = closures_by_channel_over_time(df)
    tipos = set(out["Tipo"])
    assert tipos == {"Primer cierre", "Segundo cierre"}
    assert out[out["Tipo"] == "Primer cierre"]["Total cierres"].iloc[0] == 1
    assert out[out["Tipo"] == "Segundo cierre"]["Total cierres"].iloc[0] == 1


def test_separa_las_4_etapas_de_cierre():
    """Pedido 2026-08-14: la gráfica ahora debe incluir Tercer y Cuarto
    cierre, no solo Primer/Segundo."""
    df = pd.DataFrame([
        _lead(
            "clientify - whatsapp",
            fecha_cierre=datetime(2026, 5, 1),
            fecha_segundo=datetime(2026, 5, 20),
            fecha_tercer=datetime(2026, 6, 1),
            fecha_cuarto=datetime(2026, 6, 15),
        ),
    ])
    out = closures_by_channel_over_time(df)
    tipos = set(out["Tipo"])
    assert tipos == {"Primer cierre", "Segundo cierre", "Tercer cierre", "Cuarto cierre"}
    assert out[out["Tipo"] == "Tercer cierre"]["Total cierres"].iloc[0] == 1
    assert out[out["Tipo"] == "Cuarto cierre"]["Total cierres"].iloc[0] == 1


def test_agrupa_por_anio_mes_canal_y_tipo():
    df = pd.DataFrame([
        _lead("clientify - facebook", fecha_cierre=datetime(2026, 4, 1)),
        _lead("clientify - facebook", fecha_cierre=datetime(2026, 4, 15)),
        _lead("clientify - facebook", fecha_cierre=datetime(2026, 5, 1)),
    ])
    out = closures_by_channel_over_time(df)
    abril = out[(out["Año-Mes"] == "2026-04") & (out["Canal"] == "Pauta directa") & (out["Tipo"] == "Primer cierre")]
    mayo = out[(out["Año-Mes"] == "2026-05") & (out["Canal"] == "Pauta directa") & (out["Tipo"] == "Primer cierre")]
    assert abril["Total cierres"].iloc[0] == 2
    assert mayo["Total cierres"].iloc[0] == 1


def test_canal_offline_vacio_es_referido():
    df = pd.DataFrame([
        _lead(None, fecha_cierre=datetime(2026, 4, 1)),
        _lead("", fecha_cierre=datetime(2026, 4, 2)),
    ])
    out = closures_by_channel_over_time(df)
    assert (out["Canal"] == "Referido").all()
    assert out["Total cierres"].sum() == 2


def test_fechas_nulas_no_se_cuentan():
    df = pd.DataFrame([
        _lead("clientify - facebook", fecha_cierre=pd.NaT, fecha_segundo=pd.NaT),
        _lead("clientify - facebook", fecha_cierre=datetime(2026, 4, 1)),
    ])
    out = closures_by_channel_over_time(df)
    assert out["Total cierres"].sum() == 1


def test_columnas_de_fecha_ausentes_devuelve_vacio():
    df = pd.DataFrame([{"Canal offline": "clientify - facebook"}])
    out = closures_by_channel_over_time(df)
    assert out.empty
    assert list(out.columns) == ["Año-Mes", "Canal", "Tipo", "Total cierres"]


def test_df_vacio_devuelve_vacio():
    out = closures_by_channel_over_time(pd.DataFrame())
    assert out.empty


def test_acepta_fechas_ya_parseadas_como_datetime64():
    df = pd.DataFrame({
        "Canal offline": ["clientify - facebook", "referido externo"],
        "Fecha de cierre": pd.to_datetime(["2026-04-05", "2026-04-06"]),
        "Fecha de segundo cierre": pd.to_datetime([None, None]),
    })
    out = closures_by_channel_over_time(df)
    assert out["Total cierres"].sum() == 2


def test_excluye_cierres_anteriores_a_2025():
    df = pd.DataFrame([
        _lead("clientify - facebook", fecha_cierre=datetime(2024, 12, 31)),
        _lead("clientify - facebook", fecha_cierre=datetime(2025, 1, 1)),
    ])
    out = closures_by_channel_over_time(df)
    assert list(out["Año-Mes"]) == ["2025-01"]
    assert out["Total cierres"].sum() == 1


def test_incluye_meses_y_anios_futuros_sin_fecha_de_corte_superior():
    """El filtro es 'desde 2025 en adelante' sin límite superior — debe
    seguir sumando meses futuros (2026-09, 2027, etc.) automáticamente."""
    df = pd.DataFrame([
        _lead("clientify - facebook", fecha_cierre=datetime(2026, 9, 1)),
        _lead("clientify - facebook", fecha_cierre=datetime(2027, 1, 1)),
    ])
    out = closures_by_channel_over_time(df)
    assert set(out["Año-Mes"]) == {"2026-09", "2027-01"}


def test_solo_datos_anteriores_a_2025_devuelve_vacio():
    df = pd.DataFrame([
        _lead("clientify - facebook", fecha_cierre=datetime(2024, 6, 1)),
    ])
    out = closures_by_channel_over_time(df)
    assert out.empty
