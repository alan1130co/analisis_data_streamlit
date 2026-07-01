import pandas as pd
from src.analytics.marketing_investment import (
    compute_investment_metrics,
    filter_meta_by_month,
    top_anuncios_del_mes,
)


def test_filter_meta_by_month():
    df = pd.DataFrame([
        {"Inicio del informe": pd.Timestamp("2026-04-01"), "Importe gastado (USD)": 100},
        {"Inicio del informe": pd.Timestamp("2026-03-01"), "Importe gastado (USD)": 200},
    ])
    result = filter_meta_by_month(df, 2026, 4)
    assert len(result) == 1
    assert result.iloc[0]["Importe gastado (USD)"] == 100


def test_compute_investment_metrics_calcula_costos():
    df_clientify = pd.DataFrame([
        {
            "creado": pd.Timestamp("2026-04-01"),
            "propietario": "Ana",
            "Canal offline": "Clientify - Whatsapp",
            "canal online": "paid social",
            "Motivo de no cierre": "",
            "Cantidad de cierres": 1,
            "Fecha de cierre": pd.Timestamp("2026-04-05"),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])
    df_meta = pd.DataFrame([
        {
            "Inicio del informe": pd.Timestamp("2026-04-01"),
            "Importe gastado (USD)": 1000,
            "Impresiones": 10000,
            "Alcance": 8000,
            "Clics en el enlace": 200,
            "Nuevos contactos de mensajes": 50,
            "Resultados": 5,
            "CPM (coste por 1000 impresiones) (USD)": 100,
            "Nombre del anuncio": "A1",
        },
    ])
    metrics = compute_investment_metrics(df_clientify, df_meta, 2026, 4)
    assert metrics.gasto_total == 1000.0
    assert metrics.leads_pauta == 1
    assert metrics.cierres_pauta == 1
    assert metrics.costo_por_lead == 1000.0
    assert metrics.costo_por_cierre == 1000.0
    assert metrics.cpm_promedio == 100.0  # 1000 / 10000 * 1000


def test_compute_investment_metrics_meta_vacio_no_crashea():
    df_clientify = pd.DataFrame()
    df_meta = pd.DataFrame()
    metrics = compute_investment_metrics(df_clientify, df_meta, 2026, 4)
    assert metrics.gasto_total == 0.0
    assert metrics.costo_por_lead == 0.0


def test_top_anuncios_del_mes():
    df_meta = pd.DataFrame([
        {
            "Inicio del informe": pd.Timestamp("2026-04-01"),
            "Nombre del anuncio": "Anuncio A",
            "Importe gastado (USD)": 500,
            "Impresiones": 5000,
            "Clics en el enlace": 100,
            "Nuevos contactos de mensajes": 10,
        },
        {
            "Inicio del informe": pd.Timestamp("2026-04-02"),
            "Nombre del anuncio": "Anuncio B",
            "Importe gastado (USD)": 1000,
            "Impresiones": 8000,
            "Clics en el enlace": 150,
            "Nuevos contactos de mensajes": 20,
        },
    ])
    top = top_anuncios_del_mes(df_meta, 2026, 4, top_n=2)
    assert len(top) == 2
    assert top.iloc[0]["Anuncio"] == "Anuncio B"
    assert top.iloc[0]["Costo/Contacto"] == 50.0  # 1000 / 20
