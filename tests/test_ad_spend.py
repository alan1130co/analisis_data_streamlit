"""Tests para el procesamiento de gasto en pauta publicitaria (Meta Ads)."""
import pandas as pd

from src.analytics.ad_spend import _clean_importe, monthly_ad_spend, prepare_ad_spend


def test_clean_importe_formato_europeo():
    assert _clean_importe("1.234,56") == 1234.56


def test_clean_importe_solo_coma_decimal():
    assert _clean_importe("1234,56") == 1234.56


def test_clean_importe_con_simbolos_y_espacios():
    assert _clean_importe(" $ 1.234,56 ") == 1234.56


def test_clean_importe_numero_ya_limpio():
    assert _clean_importe(1234.56) == 1234.56


def test_clean_importe_valor_vacio_o_nulo():
    assert _clean_importe(None) == 0.0
    assert _clean_importe("") == 0.0
    assert _clean_importe(pd.NA) == 0.0


def test_prepare_ad_spend_filtra_solo_usd():
    df = pd.DataFrame([
        {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "100,00"},
        {"Fecha": "02/04/2026", "Divisa": "COP", "Importe": "50000,00"},
        {"Fecha": "03/04/2026", "Divisa": "DÓLARES", "Importe": "200,00"},
        {"Fecha": "04/04/2026", "Divisa": "US Dollars", "Importe": "300,00"},
        {"Fecha": "05/04/2026", "Divisa": "DOLARES", "Importe": "400,00"},
    ])
    out = prepare_ad_spend(df)
    assert len(out) == 4
    assert out["Importe"].sum() == 1000.0


def test_prepare_ad_spend_columnas_faltantes_devuelve_vacio():
    df = pd.DataFrame([{"Fecha": "01/04/2026", "Importe": "100"}])
    out = prepare_ad_spend(df)
    assert out.empty


def test_prepare_ad_spend_fecha_invalida_se_descarta():
    df = pd.DataFrame([
        {"Fecha": "no es una fecha", "Divisa": "USD", "Importe": "100"},
        {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "200"},
    ])
    out = prepare_ad_spend(df)
    assert len(out) == 1
    assert out["Importe"].iloc[0] == 200.0


def test_prepare_ad_spend_agrega_anio_mes_num_y_mes_anio():
    df = pd.DataFrame([{"Fecha": "15/04/2026", "Divisa": "USD", "Importe": "100"}])
    out = prepare_ad_spend(df)
    assert out["Año"].iloc[0] == 2026
    assert out["Mes_num"].iloc[0] == 4
    assert out["Mes_Año"].iloc[0] == "Abril 2026"


def test_monthly_ad_spend_agrupa_y_suma_por_mes():
    df = pd.DataFrame([
        {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "100,00"},
        {"Fecha": "15/04/2026", "Divisa": "USD", "Importe": "50,00"},
        {"Fecha": "01/05/2026", "Divisa": "USD", "Importe": "200,00"},
    ])
    out = monthly_ad_spend(df)
    assert list(out["Mes_Año"]) == ["Abril 2026", "Mayo 2026"]
    assert list(out["Importe"]) == [150.0, 200.0]


def test_monthly_ad_spend_orden_cronologico_no_alfabetico():
    """'Enero' es alfabéticamente posterior a 'Diciembre' — el orden debe
    ser cronológico, no por texto."""
    df = pd.DataFrame([
        {"Fecha": "01/12/2025", "Divisa": "USD", "Importe": "100"},
        {"Fecha": "01/01/2026", "Divisa": "USD", "Importe": "200"},
    ])
    out = monthly_ad_spend(df)
    assert list(out["Mes_Año"]) == ["Diciembre 2025", "Enero 2026"]


def test_monthly_ad_spend_sin_filas_usd_devuelve_vacio():
    df = pd.DataFrame([{"Fecha": "01/04/2026", "Divisa": "COP", "Importe": "100"}])
    out = monthly_ad_spend(df)
    assert out.empty
    assert list(out.columns) == ["Mes_Año", "Importe"]


def test_monthly_ad_spend_df_vacio():
    out = monthly_ad_spend(pd.DataFrame())
    assert out.empty
