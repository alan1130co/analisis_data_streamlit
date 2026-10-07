"""Tests para el procesamiento de gasto en pauta publicitaria (Meta Ads)."""
import pandas as pd

from src.analytics.ad_spend import (
    TODOS,
    _clean_importe,
    anios_disponibles,
    avoid_label_collision_positions,
    combine_ad_spend_sources,
    combine_real_vs_billed_monthly,
    compact_month_xaxis_range,
    default_anio_index,
    filter_by_anio_mes,
    monthly_ad_spend,
    monthly_ad_spend_with_period,
    parse_mes_anio,
    prepare_ad_spend,
)


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


def test_combine_ad_spend_sources_concatena_varios_archivos():
    a = pd.DataFrame([{"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "100"}])
    b = pd.DataFrame([{"Fecha": "02/04/2026", "Divisa": "USD", "Importe": "200"}])
    out = combine_ad_spend_sources([a, b])
    assert len(out) == 2


def test_combine_ad_spend_sources_deduplica_por_id_transaccion():
    a = pd.DataFrame([
        {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "100", "Identificador de la transacción": "TX1"},
        {"Fecha": "02/04/2026", "Divisa": "USD", "Importe": "200", "Identificador de la transacción": "TX2"},
    ])
    # b (reporte nuevo) se solapa con TX2 del histórico
    b = pd.DataFrame([
        {"Fecha": "02/04/2026", "Divisa": "USD", "Importe": "200", "Identificador de la transacción": "TX2"},
        {"Fecha": "03/04/2026", "Divisa": "USD", "Importe": "300", "Identificador de la transacción": "TX3"},
    ])
    out = combine_ad_spend_sources([a, b])
    assert len(out) == 3
    assert sorted(out["Identificador de la transacción"]) == ["TX1", "TX2", "TX3"]


def test_combine_ad_spend_sources_ignora_frames_vacios_o_none():
    a = pd.DataFrame([{"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "100"}])
    out = combine_ad_spend_sources([a, None, pd.DataFrame()])
    assert len(out) == 1


def test_combine_ad_spend_sources_todos_vacios():
    out = combine_ad_spend_sources([None, pd.DataFrame()])
    assert out.empty


def test_monthly_ad_spend_with_period_conserva_anio_y_mes_num():
    df = pd.DataFrame([
        {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "100"},
        {"Fecha": "01/05/2026", "Divisa": "USD", "Importe": "200"},
    ])
    out = monthly_ad_spend_with_period(df)
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Importe"]
    assert list(out["Año"]) == [2026, 2026]
    assert list(out["Mes_num"]) == [4, 5]


def test_monthly_ad_spend_with_period_df_vacio():
    out = monthly_ad_spend_with_period(pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Importe"]


# ---------------------------------------------------------------------------
# combine_real_vs_billed_monthly — comparación real vs facturado de "Gasto
# facturado por mes (cobros de Meta)" (src/ui/sections/ad_spend_billed.py)
# ---------------------------------------------------------------------------

def test_combine_real_vs_billed_monthly_calcula_diferencia():
    real = monthly_ad_spend_with_period(pd.DataFrame([
        {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "100"},
        {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "200"},
    ]))
    facturado = monthly_ad_spend_with_period(pd.DataFrame([
        {"Fecha": "01/03/2026", "Divisa": "USD", "Importe": "80"},
        {"Fecha": "01/04/2026", "Divisa": "USD", "Importe": "200"},
    ]))

    out = combine_real_vs_billed_monthly(real, facturado)

    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Importe_Real", "Importe_Facturado", "Diferencia"]
    marzo = out[out["Mes_Año"] == "Marzo 2026"].iloc[0]
    assert marzo["Importe_Real"] == 100.0
    assert marzo["Importe_Facturado"] == 80.0
    assert marzo["Diferencia"] == 20.0
    abril = out[out["Mes_Año"] == "Abril 2026"].iloc[0]
    assert abril["Diferencia"] == 0.0


def test_combine_real_vs_billed_monthly_outer_join_mes_sin_facturar_todavia():
    """Un mes con gasto real pero sin facturación todavía (no llegó al
    umbral de Meta) debe conservarse con Importe_Facturado=0, no descartarse."""
    real = monthly_ad_spend_with_period(pd.DataFrame([
        {"Fecha": "01/05/2026", "Divisa": "USD", "Importe": "50"},
    ]))
    facturado = monthly_ad_spend_with_period(pd.DataFrame())

    out = combine_real_vs_billed_monthly(real, facturado)

    assert len(out) == 1
    assert out.iloc[0]["Importe_Real"] == 50.0
    assert out.iloc[0]["Importe_Facturado"] == 0.0
    assert out.iloc[0]["Diferencia"] == 50.0


def test_combine_real_vs_billed_monthly_mes_facturado_sin_gasto_real_registrado():
    real = monthly_ad_spend_with_period(pd.DataFrame())
    facturado = monthly_ad_spend_with_period(pd.DataFrame([
        {"Fecha": "01/06/2026", "Divisa": "USD", "Importe": "30"},
    ]))

    out = combine_real_vs_billed_monthly(real, facturado)

    assert len(out) == 1
    assert out.iloc[0]["Importe_Real"] == 0.0
    assert out.iloc[0]["Importe_Facturado"] == 30.0
    assert out.iloc[0]["Diferencia"] == -30.0


def test_combine_real_vs_billed_monthly_ambos_vacios_devuelve_vacio_con_columnas():
    out = combine_real_vs_billed_monthly(pd.DataFrame(), pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Importe_Real", "Importe_Facturado", "Diferencia"]


def test_combine_real_vs_billed_monthly_orden_cronologico():
    real = pd.DataFrame()
    facturado = monthly_ad_spend_with_period(pd.DataFrame([
        {"Fecha": "01/12/2025", "Divisa": "USD", "Importe": "10"},
        {"Fecha": "01/01/2026", "Divisa": "USD", "Importe": "20"},
    ]))
    out = combine_real_vs_billed_monthly(real, facturado)
    assert list(out["Mes_Año"]) == ["Diciembre 2025", "Enero 2026"]


# ---------------------------------------------------------------------------
# parse_mes_anio / anios_disponibles / filter_by_anio_mes — selectores
# independientes Año/Mes de las 6 gráficas de "Marketing e Inversión"
# ---------------------------------------------------------------------------

_LABELS_2_ANIOS = ["Marzo 2025", "Abril 2025", "Marzo 2026", "Septiembre 2026"]


def test_parse_mes_anio():
    assert parse_mes_anio("Marzo 2025") == (2025, 3)
    assert parse_mes_anio("Septiembre 2026") == (2026, 9)


def test_anios_disponibles_unicos_y_ordenados():
    assert anios_disponibles(_LABELS_2_ANIOS) == [2025, 2026]


# ---------------------------------------------------------------------------
# default_anio_index — default del selector "Año": año actual si está
# presente en los datos, si no "Todos" (índice 0)
# ---------------------------------------------------------------------------

def test_default_anio_index_anio_actual_presente():
    assert default_anio_index([2024, 2025, 2026], 2026) == 3  # TODOS=0, 2024=1, 2025=2, 2026=3


def test_default_anio_index_anio_actual_es_el_unico():
    assert default_anio_index([2026], 2026) == 1


def test_default_anio_index_anio_actual_ausente_cae_a_todos():
    assert default_anio_index([2024, 2025], 2026) == 0


def test_default_anio_index_lista_vacia_cae_a_todos():
    assert default_anio_index([], 2026) == 0


def test_filter_by_anio_mes_todos_todos_devuelve_todo():
    assert filter_by_anio_mes(_LABELS_2_ANIOS, TODOS, TODOS) == _LABELS_2_ANIOS


def test_filter_by_anio_mes_anio_especifico_mes_todos():
    """Año=2025, Mes=Todos → todos los meses de 2025."""
    assert filter_by_anio_mes(_LABELS_2_ANIOS, 2025, TODOS) == ["Marzo 2025", "Abril 2025"]


def test_filter_by_anio_mes_anio_todos_mes_especifico():
    """Año=Todos, Mes=Marzo → Marzo de TODOS los años (comparación año
    contra año, caso intencional, no un error)."""
    assert filter_by_anio_mes(_LABELS_2_ANIOS, TODOS, "Marzo") == ["Marzo 2025", "Marzo 2026"]


def test_filter_by_anio_mes_anio_y_mes_especificos():
    assert filter_by_anio_mes(_LABELS_2_ANIOS, 2026, "Septiembre") == ["Septiembre 2026"]


def test_filter_by_anio_mes_combinacion_sin_datos_devuelve_vacio():
    assert filter_by_anio_mes(_LABELS_2_ANIOS, 2025, "Septiembre") == []


# ---------------------------------------------------------------------------
# compact_month_xaxis_range — eje X compacto (una sola barra) en
# ad_spend_roas.py / ad_spend_total_roas.py cuando Año+Mes son específicos
# ---------------------------------------------------------------------------

def test_compact_month_xaxis_range_anio_y_mes_especificos():
    assert compact_month_xaxis_range(_LABELS_2_ANIOS, 2026, "Septiembre") == (3 - 0.5, 3 + 0.5)


def test_compact_month_xaxis_range_anio_todos_devuelve_none():
    assert compact_month_xaxis_range(_LABELS_2_ANIOS, TODOS, "Marzo") is None


def test_compact_month_xaxis_range_mes_todos_devuelve_none():
    assert compact_month_xaxis_range(_LABELS_2_ANIOS, 2025, TODOS) is None


def test_compact_month_xaxis_range_ambos_todos_devuelve_none():
    assert compact_month_xaxis_range(_LABELS_2_ANIOS, TODOS, TODOS) is None


def test_compact_month_xaxis_range_etiqueta_no_encontrada_devuelve_none():
    """Combinación Año+Mes específicos pero sin datos en categoryarray
    (p.ej. filtro sin coincidencias) — no hay índice que devolver."""
    assert compact_month_xaxis_range(_LABELS_2_ANIOS, 2025, "Septiembre") is None


# ---------------------------------------------------------------------------
# avoid_label_collision_positions — anti-colisión de etiquetas en gráficas de
# barras + línea (ad_spend_cost_per_lead.py, ad_spend_vs_closures.py,
# ad_spend_roas.py, ad_spend_total_roas.py, ad_spend_vs_process_value_roas.py)
# ---------------------------------------------------------------------------

def test_avoid_label_collision_positions_misma_altura_normalizada_manda_abajo():
    """Barra al 90% de su eje y línea al 92% del suyo (fracciones muy
    cercanas, aunque los valores crudos sean totalmente distintos:
    $7,656.03 vs $390.67) -> colisión -> la etiqueta de la línea se manda
    abajo del marcador."""
    positions = avoid_label_collision_positions(
        categories=["Marzo 2025"],
        values=[390.67],
        axis_max=423.0,  # 390.67 / 423.0 ~= 0.923
        reference_categories=["Marzo 2025"],
        reference_values=[7656.03],
        reference_axis_max=8500.0,  # 7656.03 / 8500.0 ~= 0.901
    )
    assert positions == ["bottom center"]


def test_avoid_label_collision_positions_alturas_distintas_mantiene_arriba():
    """Barra baja (20% de su eje) y línea alta (90% del suyo) -> sin
    colisión -> se mantiene "top center" (comportamiento actual)."""
    positions = avoid_label_collision_positions(
        categories=["Marzo 2025"],
        values=[90.0],
        axis_max=100.0,
        reference_categories=["Marzo 2025"],
        reference_values=[20.0],
        reference_axis_max=100.0,
    )
    assert positions == ["top center"]


def test_avoid_label_collision_positions_categoria_sin_referencia_mantiene_arriba():
    """Un mes que la línea trae pero que no tiene barra visible (filtrado
    por Año/Mes puntual en las gráficas de ROAS, ver `ad_spend_roas.py`) no
    tiene con qué chocar -> "top center"."""
    positions = avoid_label_collision_positions(
        categories=["Abril 2025"],
        values=[50.0],
        axis_max=100.0,
        reference_categories=["Marzo 2025"],
        reference_values=[90.0],
        reference_axis_max=100.0,
    )
    assert positions == ["top center"]


def test_avoid_label_collision_positions_toma_la_fraccion_mas_alta_entre_barras_repetidas():
    """Barras agrupadas (2 series) para el mismo mes — se compara contra la
    MÁS ALTA de las 2 (la que de verdad compite por el mismo espacio
    vertical), no contra un promedio ni la primera que aparezca."""
    positions = avoid_label_collision_positions(
        categories=["Marzo 2025"],
        values=[88.0],
        axis_max=100.0,
        reference_categories=["Marzo 2025", "Marzo 2025"],
        reference_values=[10.0, 90.0],  # la 2da barra (90) sí colisiona
        reference_axis_max=100.0,
    )
    assert positions == ["bottom center"]


def test_avoid_label_collision_positions_varios_puntos_mezcla_arriba_y_abajo():
    positions = avoid_label_collision_positions(
        categories=["Marzo 2025", "Abril 2025"],
        values=[90.0, 20.0],
        axis_max=100.0,
        reference_categories=["Marzo 2025", "Abril 2025"],
        reference_values=[92.0, 95.0],
        reference_axis_max=100.0,
    )
    assert positions == ["bottom center", "top center"]


def test_avoid_label_collision_positions_valores_cero_no_rompen():
    positions = avoid_label_collision_positions(
        categories=["Marzo 2025"],
        values=[0.0],
        axis_max=100.0,
        reference_categories=["Marzo 2025"],
        reference_values=[0.0],
        reference_axis_max=0.0,
    )
    assert positions == ["top center"]


def test_avoid_label_collision_positions_listas_vacias_devuelve_vacio():
    assert avoid_label_collision_positions([], [], 1.0, [], [], 1.0) == []
