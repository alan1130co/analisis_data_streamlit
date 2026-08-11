"""Tests para la comparación de Cierres vs Segundos Cierres por Año-Mes."""
from datetime import datetime

import pandas as pd

from src.analytics.closures_vs_second_closures import closures_vs_second_closures


def _lead(fecha_cierre=pd.NaT, fecha_segundo=pd.NaT):
    return {
        "Fecha de cierre": fecha_cierre,
        "Fecha de segundo cierre": fecha_segundo,
    }


def test_agrupa_por_anio_mes():
    df = pd.DataFrame([
        _lead(fecha_cierre=datetime(2026, 4, 5)),
        _lead(fecha_cierre=datetime(2026, 4, 10)),
        _lead(fecha_cierre=datetime(2026, 5, 1)),
    ])
    out = closures_vs_second_closures(df)
    assert list(out["Año-Mes"]) == ["2026-04", "2026-05"]
    assert list(out["Cierres"]) == [2, 1]
    assert list(out["Segundos cierres"]) == [0, 0]


def test_segundos_cierres_se_cuentan_por_separado():
    df = pd.DataFrame([
        _lead(fecha_cierre=datetime(2026, 4, 5)),
        _lead(fecha_segundo=datetime(2026, 4, 20)),
        _lead(fecha_segundo=datetime(2026, 5, 3)),
    ])
    out = closures_vs_second_closures(df)
    row_abril = out[out["Año-Mes"] == "2026-04"].iloc[0]
    row_mayo = out[out["Año-Mes"] == "2026-05"].iloc[0]
    assert row_abril["Cierres"] == 1
    assert row_abril["Segundos cierres"] == 1
    assert row_mayo["Cierres"] == 0
    assert row_mayo["Segundos cierres"] == 1


def test_meses_sin_alguna_de_las_dos_metricas_rellenan_con_cero():
    df = pd.DataFrame([
        _lead(fecha_cierre=datetime(2026, 6, 1)),
    ])
    out = closures_vs_second_closures(df)
    assert out["Cierres"].dtype.kind == "i"
    assert out["Segundos cierres"].dtype.kind == "i"
    assert out.loc[0, "Segundos cierres"] == 0


def test_fechas_nulas_no_se_cuentan():
    df = pd.DataFrame([
        _lead(fecha_cierre=pd.NaT, fecha_segundo=pd.NaT),
        _lead(fecha_cierre=datetime(2026, 4, 1)),
    ])
    out = closures_vs_second_closures(df)
    assert list(out["Cierres"]) == [1]


def test_resultado_ordenado_cronologicamente():
    df = pd.DataFrame([
        _lead(fecha_cierre=datetime(2026, 8, 1)),
        _lead(fecha_cierre=datetime(2026, 3, 1)),
        _lead(fecha_cierre=datetime(2026, 5, 1)),
    ])
    out = closures_vs_second_closures(df)
    assert list(out["Año-Mes"]) == ["2026-03", "2026-05", "2026-08"]


def test_columnas_ausentes_devuelve_vacio():
    df = pd.DataFrame([{"otra_columna": 1}])
    out = closures_vs_second_closures(df)
    assert out.empty
    assert list(out.columns) == ["Año-Mes", "Cierres", "Segundos cierres"]


def test_df_vacio_devuelve_vacio():
    out = closures_vs_second_closures(pd.DataFrame())
    assert out.empty


def test_acepta_fechas_ya_parseadas_como_datetime64():
    """La columna real ya viene parseada por ExcelContactsLoader (datetime64),
    no como string dd/mm/aaaa crudo — debe seguir funcionando igual."""
    df = pd.DataFrame({
        "Fecha de cierre": pd.to_datetime(["2026-04-05", None]),
        "Fecha de segundo cierre": pd.to_datetime([None, "2026-04-10"]),
    })
    out = closures_vs_second_closures(df)
    assert list(out["Año-Mes"]) == ["2026-04"]
    assert out.loc[0, "Cierres"] == 1
    assert out.loc[0, "Segundos cierres"] == 1
