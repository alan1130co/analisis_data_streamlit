"""Tests para el cruce de gasto en pauta vs cierres con origen en redes."""
import pandas as pd

from src.analytics.ad_spend_vs_closures import (
    calculate_redes_initial_payments_chart,
    calculate_redes_revenue_chart,
    closures_from_redes_monthly,
    closures_from_redes_total_monthly,
    combine_ad_spend_and_closures,
    combine_ad_spend_and_cost_per_lead,
    combine_ad_spend_and_revenue,
    combine_ad_spend_revenue_and_roas,
    combine_ad_spend_total_revenue_and_roas,
    revenue_cuota_inicial_from_redes_monthly,
    revenue_from_redes_monthly,
)
from src.analytics.metrics import CLOSE_DATE_COLS, is_organico, is_tiktok, valid_closure_estado_mask
from src.config.settings import (
    HONORARIOS_ALEXA_USD,
    HONORARIOS_EQUIPO_MARKETING_USD,
    HONORARIOS_HELEN_USD,
    HONORARIOS_JEFE_CTO_USD,
    MARKETING_OFFLINE_CHANNELS,
    SALARIO_USUARIO_COP,
    SALARIO_USUARIO_USD,
    USD_COP_EXCHANGE_RATE,
)


def test_closures_from_redes_monthly_cuenta_primer_y_segundo_cierre():
    df = pd.DataFrame([
        {
            "Canal offline": "Clientify - Instagram",
            "Fecha de cierre": "01/04/2026",
            "Fecha de segundo cierre": None,
        },
        {
            "Canal offline": "Clientify - Facebook",
            "Fecha de cierre": None,
            "Fecha de segundo cierre": "15/04/2026",
        },
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Mes_Año"].iloc[0] == "Abril 2026"
    assert out["Cierres_Redes"].iloc[0] == 2


def test_closures_from_redes_monthly_excluye_referido_puro():
    df = pd.DataFrame([
        {"Canal offline": "referido puro", "Fecha de cierre": "01/04/2026", "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_monthly(df)
    assert out.empty


def test_closures_from_redes_monthly_comparacion_insensible_a_mayusculas():
    """El 'Canal offline' real ya viene lower+strip por el loader, pero
    `is_tiktok`/`MARKETING_OFFLINE_CHANNELS` deben igual matchear variantes
    en mayúsculas."""
    df = pd.DataFrame([
        {"Canal offline": "tiktok", "Fecha de cierre": "05/06/2026", "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 1


def test_closures_from_redes_monthly_incluye_organico_por_canal_offline():
    """Regresión: el whitelist anterior (`PAUTA_DIRECTA_ORIGENES`) no incluía
    Orgánico en absoluto — la nueva definición unificada (`MARKETING_OFFLINE_
    CHANNELS` ∪ Orgánico ∪ TikTok) sí debe contarlo."""
    df = pd.DataFrame([
        {"Canal offline": "organico", "Fecha de cierre": "01/04/2026", "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 1


def test_closures_from_redes_monthly_incluye_tiktok_por_origen_de_la_pauta():
    """`is_tiktok` también mira 'Origen de la pauta', no solo 'Canal
    offline' — debe contar igual."""
    df = pd.DataFrame([
        {"Canal offline": "", "Origen de la pauta": "tiktok", "Fecha de cierre": "01/04/2026",
         "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 1


def test_closures_from_redes_monthly_incluye_canales_de_marketing_offline_channels():
    """Los canales exactos de `settings.MARKETING_OFFLINE_CHANNELS` que no
    empiezan con 'Clientify -' (Formulario web, Llamada Entrante) también
    deben contar."""
    df = pd.DataFrame([
        {"Canal offline": "Formulario web", "Fecha de cierre": "01/04/2026", "Fecha de segundo cierre": None},
        {"Canal offline": "Llamada Entrante", "Fecha de cierre": "02/04/2026", "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 2


def test_closures_from_redes_monthly_incluye_referido_cliente_activo_redes():
    """'Referido cliente activo - Redes' está agregado explícitamente en
    `redes_channel_mask` (2026-08-13c) aunque no matchee
    `MARKETING_OFFLINE_CHANNELS` ni Orgánico/TikTok — el negocio lo cuenta
    como "redes" para el volumen de cierres."""
    df = pd.DataFrame([
        {"Canal offline": "Referido cliente activo - Redes", "Fecha de cierre": "01/04/2026",
         "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 1


def test_closures_from_redes_monthly_sin_restriccion_temporal():
    """A diferencia de `closures_by_channel_over_time` (filtrado desde
    2025), esta serie mensual no debe descartar años anteriores a 2025 ni
    tener ningún límite superior — debe aplicar igual a todo el histórico."""
    df = pd.DataFrame([
        {"Canal offline": "Clientify - Facebook", "Fecha de cierre": "01/03/2024", "Fecha de segundo cierre": None},
        {"Canal offline": "Clientify - Facebook", "Fecha de cierre": "01/03/2030", "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_monthly(df)
    assert set(out["Mes_Año"]) == {"Marzo 2024", "Marzo 2030"}


def test_closures_from_redes_monthly_cuenta_tercer_y_cuarto_cierre():
    """Regresión: antes solo miraba Primer + Segundo cierre, lo que hacía
    que el total mensual de la gráfica no coincidiera con el consolidado
    global (que sí cuenta las 4 fechas de cierre, ver `metrics.CLOSE_DATE_COLS`)."""
    df = pd.DataFrame([
        {"Canal offline": "Clientify - Instagram", "Fecha de cierre": "01/04/2026",
         "Fecha de segundo cierre": None, "Fecha de tercer cierre": None, "Fecha de 4to cierre": None},
        {"Canal offline": "Clientify - Facebook", "Fecha de cierre": None,
         "Fecha de segundo cierre": None, "Fecha de tercer cierre": "10/04/2026", "Fecha de 4to cierre": None},
        {"Canal offline": "tiktok", "Fecha de cierre": None,
         "Fecha de segundo cierre": None, "Fecha de tercer cierre": None, "Fecha de 4to cierre": "20/04/2026"},
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 3


def test_closures_from_redes_monthly_excluye_estado_inactivo():
    """Mismo criterio de validez (`estado != 'inactivo'`) que usa el resto
    de la sección de Gestión Comercial — antes esta gráfica no filtraba por
    estado en absoluto."""
    df = pd.DataFrame([
        {"Canal offline": "Clientify - Instagram", "Fecha de cierre": "01/04/2026",
         "Fecha de segundo cierre": None, "estado": "inactivo"},
        {"Canal offline": "Clientify - Facebook", "Fecha de cierre": "05/04/2026",
         "Fecha de segundo cierre": None, "estado": "activo"},
    ])
    out = closures_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 1


def test_closures_from_redes_monthly_coincide_con_total_global():
    """El total sumado de 'Cierres_Redes' (across meses) debe coincidir
    exactamente con contar a mano, de forma independiente, los eventos de
    cierre válidos en las 4 columnas de fecha para leads de canal redes —
    el mismo criterio (`CLOSE_DATE_COLS` + `valid_closure_estado_mask`) que
    usa el resto de Gestión Comercial (KPI "Total Cierres", eficiencias)."""
    df = pd.DataFrame([
        {
            "Canal offline": "Clientify - Instagram", "estado": "activo",
            "Fecha de cierre": "01/07/2025", "Fecha de segundo cierre": "15/07/2025",
            "Fecha de tercer cierre": "20/08/2025", "Fecha de 4to cierre": None,
        },
        {
            "Canal offline": "Clientify - Facebook", "estado": "activo - mora",
            "Fecha de cierre": None, "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": "05/07/2025",
        },
        {
            # Canal de redes pero estado inactivo -> no debe contar.
            "Canal offline": "Tiktok", "estado": "inactivo",
            "Fecha de cierre": "10/07/2025", "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        },
        {
            # Cierre válido pero fuera del set de canales "redes" -> no debe contar.
            "Canal offline": "referido puro", "estado": "activo",
            "Fecha de cierre": "12/07/2025", "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        },
        {
            # Origen extra agregado explícitamente a redes_channel_mask -> sí debe contar.
            "Canal offline": "Referido cliente activo - Redes", "estado": "activo",
            "Fecha de cierre": "18/07/2025", "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
        },
    ])
    out = closures_from_redes_monthly(df)

    # Recomputado de forma independiente (sin reusar `redes_channel_mask`)
    # a partir de las mismas piezas ya probadas por separado en
    # `test_metrics.py`: MARKETING_OFFLINE_CHANNELS ∪ Orgánico ∪ TikTok ∪
    # "Referido cliente activo - Redes".
    valid = valid_closure_estado_mask(df)
    canal_norm = df["Canal offline"].str.strip().str.lower()
    marketing_mask = canal_norm.isin(MARKETING_OFFLINE_CHANNELS)
    organico_mask = df.apply(is_organico, axis=1)
    tiktok_mask = df.apply(is_tiktok, axis=1)
    referido_redes_mask = canal_norm == "referido cliente activo - redes"
    redes_mask = valid & (marketing_mask | organico_mask | tiktok_mask | referido_redes_mask)
    expected_total = sum(int(df.loc[redes_mask, col].notna().sum()) for col in CLOSE_DATE_COLS)

    assert expected_total == 5
    assert out["Cierres_Redes"].sum() == expected_total


def test_closures_from_redes_monthly_df_vacio():
    out = closures_from_redes_monthly(pd.DataFrame())
    assert out.empty


def test_closures_from_redes_monthly_sin_columna_canal_offline():
    df = pd.DataFrame([{"Fecha de cierre": "01/04/2026"}])
    out = closures_from_redes_monthly(df)
    assert out.empty


def test_combine_ad_spend_and_closures_cruza_por_mes_ano():
    gasto = pd.DataFrame([
        {"Mes_Año": "Abril 2026", "Importe": 100.0},
        {"Mes_Año": "Mayo 2026", "Importe": 200.0},
    ])
    cierres = pd.DataFrame([
        {"Año": 2026, "Mes_num": 4, "Mes_Año": "Abril 2026", "Cierres_Redes": 3},
    ])
    out = combine_ad_spend_and_closures(gasto, cierres)
    assert list(out["Mes_Año"]) == ["Abril 2026", "Mayo 2026"]
    assert list(out["Cierres_Redes"]) == [3, 0]


def test_combine_ad_spend_and_closures_sin_cierres_devuelve_cero():
    gasto = pd.DataFrame([{"Mes_Año": "Abril 2026", "Importe": 100.0}])
    out = combine_ad_spend_and_closures(gasto, pd.DataFrame())
    assert list(out["Cierres_Redes"]) == [0]


def test_combine_ad_spend_and_closures_gasto_vacio():
    out = combine_ad_spend_and_closures(pd.DataFrame(), pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["Mes_Año", "Importe", "Cierres_Redes"]


def test_closures_from_redes_total_monthly_incluye_tiktok():
    """Regla de negocio 2026-08-13d: el costo por lead ahora se calcula
    sobre el VOLUMEN TOTAL de redes (incluye Orgánico/TikTok), a diferencia
    de las funciones de ingreso/ROAS que siguen excluyéndolo."""
    df = pd.DataFrame([
        {"Canal offline": "tiktok", "Fecha de cierre": "05/06/2026", "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_total_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 1

    # Debe coincidir exactamente con `closures_from_redes_monthly` (mismo
    # criterio, sin restricción de canal) — ya no es un subconjunto.
    out_full = closures_from_redes_monthly(df)
    pd.testing.assert_frame_equal(out, out_full)


def test_closures_from_redes_total_monthly_cuenta_canales_pagos():
    df = pd.DataFrame([
        {"Canal offline": "Clientify - Instagram", "Fecha de cierre": "10/06/2026", "Fecha de segundo cierre": None},
    ])
    out = closures_from_redes_total_monthly(df)
    assert len(out) == 1
    assert out["Cierres_Redes"].iloc[0] == 1


def test_combine_ad_spend_and_cost_per_lead_calcula_valor_por_lead():
    gasto = pd.DataFrame([
        {"Mes_Año": "Abril 2026", "Importe": 100.0},
        {"Mes_Año": "Mayo 2026", "Importe": 200.0},
    ])
    cierres = pd.DataFrame([
        {"Año": 2026, "Mes_num": 4, "Mes_Año": "Abril 2026", "Cierres_Redes": 4},
    ])
    out = combine_ad_spend_and_cost_per_lead(gasto, cierres)
    assert list(out["Valor_por_Lead"]) == [25.0, 0.0]


def test_combine_ad_spend_and_cost_per_lead_gasto_vacio():
    out = combine_ad_spend_and_cost_per_lead(pd.DataFrame(), pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["Mes_Año", "Importe", "Cierres_Redes", "Valor_por_Lead"]


def test_combine_ad_spend_and_cost_per_lead_caso_julio_volumen_total_de_redes():
    """Caso concreto pedido por el negocio (2026-08-13d): $4,444.05 de gasto
    en julio dividido entre 19 cierres (volumen TOTAL de redes, incluye
    Orgánico/TikTok/"Referido cliente activo - Redes") debe dar ~$233.89 de
    costo promedio por lead."""
    gasto = pd.DataFrame([{"Mes_Año": "Julio 2025", "Importe": 4444.05}])
    cierres = pd.DataFrame([
        {"Año": 2025, "Mes_num": 7, "Mes_Año": "Julio 2025", "Cierres_Redes": 19},
    ])
    out = combine_ad_spend_and_cost_per_lead(gasto, cierres)
    assert out["Cierres_Redes"].iloc[0] == 19
    assert abs(out["Valor_por_Lead"].iloc[0] - 233.89) < 0.01


def test_costo_por_lead_e_ingreso_total_incluyen_organico_pero_roas_lo_mantiene_excluido():
    """Prueba lado a lado (2026-08-13d/e): sobre el MISMO dataset, el
    denominador del costo por lead y el ingreso por valor total del proceso
    ven el volumen total de redes (incluyen Orgánico), pero el ingreso por
    cuota inicial (que alimenta ROAS) se mantiene estricto a pauta paga."""
    df = pd.DataFrame([
        {
            "Canal offline": "organico",
            "Fecha de cierre": "01/07/2025", "Fecha de segundo cierre": None,
            "Valor total del proceso": "1000", "Cuota inicial pactada": "300",
        },
        {
            "Canal offline": "Clientify - Facebook",
            "Fecha de cierre": "02/07/2025", "Fecha de segundo cierre": None,
            "Valor total del proceso": "2000", "Cuota inicial pactada": "600",
        },
    ])

    cierres = closures_from_redes_total_monthly(df)
    assert cierres["Cierres_Redes"].iloc[0] == 2  # Orgánico + pauta paga

    ingreso = revenue_from_redes_monthly(df)
    assert ingreso["Ingreso_Redes"].iloc[0] == 3000.0  # Orgánico (1000) + pauta paga (2000)

    ingreso_cuota_inicial = revenue_cuota_inicial_from_redes_monthly(df)
    assert ingreso_cuota_inicial["Ingreso_CuotaInicial"].iloc[0] == 600.0  # solo pauta paga (ROAS)


def test_revenue_from_redes_monthly_suma_valor_total_del_proceso():
    df = pd.DataFrame([
        {
            "Canal offline": "Clientify - Instagram",
            "Fecha de cierre": "01/04/2026",
            "Fecha de segundo cierre": None,
            "Valor total del proceso": "1.500,00",
        },
        {
            "Canal offline": "Clientify - Facebook",
            "Fecha de cierre": None,
            "Fecha de segundo cierre": "15/04/2026",
            "Valor total del proceso": "500,00",
        },
    ])
    out = revenue_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Mes_Año"].iloc[0] == "Abril 2026"
    assert out["Ingreso_Redes"].iloc[0] == 2000.0


def test_revenue_from_redes_monthly_incluye_tiktok():
    """Regla de negocio 2026-08-13e: `revenue_from_redes_monthly` pasó a
    usar el volumen total de redes (`redes_channel_mask`), ya no el
    subconjunto pagado — a diferencia de `revenue_cuota_inicial_from_redes_
    monthly` (ROAS), que sigue excluyendo TikTok."""
    df = pd.DataFrame([
        {
            "Canal offline": "tiktok",
            "Fecha de cierre": "01/04/2026",
            "Fecha de segundo cierre": None,
            "Valor total del proceso": "1000",
        },
    ])
    out = revenue_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Ingreso_Redes"].iloc[0] == 1000.0

    out_cuota_inicial = revenue_cuota_inicial_from_redes_monthly(
        pd.DataFrame([{**df.iloc[0].to_dict(), "Cuota inicial pactada": "1000"}])
    )
    assert out_cuota_inicial.empty


def test_revenue_from_redes_monthly_usa_las_4_columnas_de_cierre_y_filtra_estado():
    """Verificación (punto 2 del pedido 2026-08-13e): igual que
    `closures_from_redes_monthly`, debe recorrer las 4 columnas de fecha de
    cierre y excluir estado 'inactivo' al asignar el mes."""
    df = pd.DataFrame([
        {
            "Canal offline": "tiktok", "estado": "activo",
            "Fecha de cierre": None, "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": "20/08/2025", "Fecha de 4to cierre": None,
            "Valor total del proceso": "700",
        },
        {
            # Estado inválido -> no debe contar pese a tener fecha de cierre.
            "Canal offline": "organico", "estado": "inactivo",
            "Fecha de cierre": "05/07/2025", "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
            "Valor total del proceso": "9999",
        },
    ])
    out = revenue_from_redes_monthly(df)
    assert list(out["Mes_Año"]) == ["Agosto 2025"]
    assert out["Ingreso_Redes"].iloc[0] == 700.0


def test_revenue_from_redes_monthly_coincide_con_volumen_total_por_mes():
    """Verificación (punto 4 del pedido 2026-08-13e): la suma mensual de
    "Valor total del proceso" debe coincidir con recomputar a mano, de forma
    independiente, sobre la misma máscara unificada de canales
    (`MARKETING_OFFLINE_CHANNELS` ∪ Orgánico ∪ TikTok ∪ "Referido cliente
    activo - Redes") + `CLOSE_DATE_COLS` + `valid_closure_estado_mask` — las
    mismas piezas que ya prueba `closures_from_redes_monthly`."""
    df = pd.DataFrame([
        {
            "Canal offline": "organico", "estado": "activo",
            "Fecha de cierre": "01/07/2025", "Fecha de segundo cierre": "15/08/2025",
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
            "Valor total del proceso": "1.000,00",
        },
        {
            "Canal offline": "Referido cliente activo - Redes", "estado": "activo - mora",
            "Fecha de cierre": None, "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": "20/07/2025", "Fecha de 4to cierre": None,
            "Valor total del proceso": "2.500,50",
        },
        {
            # Canal de redes pero estado inactivo -> no debe contar.
            "Canal offline": "tiktok", "estado": "inactivo",
            "Fecha de cierre": "05/07/2025", "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
            "Valor total del proceso": "9999",
        },
        {
            # Cierre válido pero fuera del set de canales "redes" -> no debe contar.
            "Canal offline": "referido puro", "estado": "activo",
            "Fecha de cierre": "07/07/2025", "Fecha de segundo cierre": None,
            "Fecha de tercer cierre": None, "Fecha de 4to cierre": None,
            "Valor total del proceso": "500",
        },
    ])
    out = revenue_from_redes_monthly(df)

    julio = out[out["Mes_Año"] == "Julio 2025"]
    assert julio["Ingreso_Redes"].iloc[0] == 1000.0 + 2500.50

    agosto = out[out["Mes_Año"] == "Agosto 2025"]
    assert agosto["Ingreso_Redes"].iloc[0] == 1000.0


def test_revenue_from_redes_monthly_sin_columna_valor_devuelve_vacio():
    df = pd.DataFrame([
        {"Canal offline": "Clientify - Instagram", "Fecha de cierre": "01/04/2026", "Fecha de segundo cierre": None},
    ])
    out = revenue_from_redes_monthly(df)
    assert out.empty


# --- calculate_redes_revenue_chart (2026-08-13f, función aislada para la
# gráfica "Gasto en pauta vs Ingresos por redes") ---------------------------

def _fila_multietapa(canal_offline, estado="activo", canal_online=None, **fechas_y_valores):
    row = {"Canal offline": canal_offline, "estado": estado, "canal online": canal_online}
    for date_col in [
        "Fecha de cierre", "Fecha de segundo cierre", "Fecha de tercer cierre", "Fecha de 4to cierre",
    ]:
        row.setdefault(date_col, None)
    for value_col in [
        "Valor total del proceso", "Valor total segundo cierre",
        "Valor total tercer cierre", "Valor total 4to cierre",
    ]:
        row.setdefault(value_col, None)
    row.update(fechas_y_valores)
    return row


def test_calculate_redes_revenue_chart_usa_el_campo_de_valor_correcto_por_etapa():
    """Reproduce el caso real verificado (2026-08-13f, contacto 'Fredy
    Arturo Tobar Benavides' en un export real de Clientify): su PRIMER
    cierre fue en enero ($6.000, fuera del mes evaluado) y su SEGUNDO cierre
    fue en julio, con 'Valor total segundo cierre' = $3.500 — NO debe
    reusarse el valor de la primera etapa ($6.000) para la segunda."""
    df = pd.DataFrame([
        _fila_multietapa(
            "Clientify - Whatsapp", canal_online="paid social",
            **{
                "Fecha de cierre": "19/01/2026", "Valor total del proceso": "6000",
                "Fecha de segundo cierre": "14/07/2026", "Valor total segundo cierre": "3500",
            },
        ),
    ])
    out = calculate_redes_revenue_chart(df)

    enero = out[out["Mes_Año"] == "Enero 2026"]
    assert enero["Ingreso_Redes"].iloc[0] == 6000.0

    julio = out[out["Mes_Año"] == "Julio 2026"]
    assert julio["Ingreso_Redes"].iloc[0] == 3500.0  # NO 6000.0


def test_calculate_redes_revenue_chart_evalua_las_4_etapas_con_su_propio_campo():
    df = pd.DataFrame([
        _fila_multietapa(
            "Tiktok",
            **{
                "Fecha de cierre": "01/07/2026", "Valor total del proceso": "1000",
                "Fecha de segundo cierre": "02/07/2026", "Valor total segundo cierre": "2000",
                "Fecha de tercer cierre": "03/07/2026", "Valor total tercer cierre": "3000",
                "Fecha de 4to cierre": "04/07/2026", "Valor total 4to cierre": "4000",
            },
        ),
    ])
    out = calculate_redes_revenue_chart(df)
    assert out["Ingreso_Redes"].iloc[0] == 1000.0 + 2000.0 + 3000.0 + 4000.0


def test_calculate_redes_revenue_chart_incluye_organico_y_referido_redes():
    df = pd.DataFrame([
        _fila_multietapa("Organico", **{"Fecha de cierre": "01/07/2026", "Valor total del proceso": "6000"}),
        _fila_multietapa(
            "Referido cliente activo - Redes",
            **{"Fecha de cierre": "02/07/2026", "Valor total del proceso": "6000"},
        ),
    ])
    out = calculate_redes_revenue_chart(df)
    assert out["Ingreso_Redes"].iloc[0] == 12000.0


def test_calculate_redes_revenue_chart_incluye_canal_online_paid_social():
    """Cruce explícito pedido (2026-08-13f): un 'Canal offline' que no
    matchea ninguna categoría conocida, pero con canal online='paid social',
    debe igual contar."""
    df = pd.DataFrame([
        _fila_multietapa(
            "algun canal nuevo no listado", canal_online="paid social",
            **{"Fecha de cierre": "01/07/2026", "Valor total del proceso": "6000"},
        ),
    ])
    out = calculate_redes_revenue_chart(df)
    assert len(out) == 1
    assert out["Ingreso_Redes"].iloc[0] == 6000.0


def test_calculate_redes_revenue_chart_excluye_estado_inactivo():
    df = pd.DataFrame([
        _fila_multietapa(
            "Tiktok", estado="inactivo",
            **{"Fecha de cierre": "01/07/2026", "Valor total del proceso": "6000"},
        ),
    ])
    out = calculate_redes_revenue_chart(df)
    assert out.empty


def test_calculate_redes_revenue_chart_excluye_canal_fuera_de_redes():
    df = pd.DataFrame([
        _fila_multietapa("referido puro", **{"Fecha de cierre": "01/07/2026", "Valor total del proceso": "6000"}),
    ])
    out = calculate_redes_revenue_chart(df)
    assert out.empty


def test_calculate_redes_revenue_chart_df_vacio():
    out = calculate_redes_revenue_chart(pd.DataFrame())
    assert out.empty


def test_calculate_redes_revenue_chart_no_afecta_revenue_from_redes_monthly():
    """Aislamiento (punto 1 del pedido 2026-08-13f): el bug de reusar
    'Valor total del proceso' para las 4 etapas sigue presente en
    `revenue_from_redes_monthly` a propósito — esta función NO lo tocó, y
    `revenue_cuota_inicial_from_redes_monthly` (ROAS) tampoco cambió."""
    df = pd.DataFrame([
        _fila_multietapa(
            "Clientify - Whatsapp", canal_online="paid social",
            **{
                "Fecha de cierre": "19/01/2026", "Valor total del proceso": "6000",
                "Fecha de segundo cierre": "14/07/2026", "Valor total segundo cierre": "3500",
                "Cuota inicial pactada": "1000",
            },
        ),
    ])
    out_legacy = revenue_from_redes_monthly(df)
    julio_legacy = out_legacy[out_legacy["Mes_Año"] == "Julio 2026"]
    # Comportamiento previo (no corregido a propósito): reusa "Valor total
    # del proceso" ($6000) para el segundo cierre en vez de $3500.
    assert julio_legacy["Ingreso_Redes"].iloc[0] == 6000.0

    out_roas = revenue_cuota_inicial_from_redes_monthly(df)
    julio_roas = out_roas[out_roas["Mes_Año"] == "Julio 2026"]
    # Comportamiento previo (tampoco tocado): "Clientify - Whatsapp" sí está
    # en REDES_PAGAS_ORIGENES, y reusa "Cuota inicial pactada" ($1000) para
    # el segundo cierre igual que antes de este cambio.
    assert julio_roas["Ingreso_CuotaInicial"].iloc[0] == 1000.0


def test_calculate_redes_revenue_chart_acceptance_boris_y_fredy():
    """Criterio de aceptación (2026-08-13f), reproducido con datos
    sintéticos que replican EXACTAMENTE los dos contactos reales verificados
    contra un export real de Clientify (13/08/2026):

    - Boris Andrés Reyes Álvarez: Clientify - Whatsapp, paid social,
      primer cierre 29/07/2026, $8.000 -> coincide con lo reportado.
    - Fredy Arturo Tobar Benavides: Clientify - Whatsapp, paid social,
      primer cierre 19/01/2026 ($6.000, FUERA de julio), segundo cierre
      14/07/2026, $3.500 (el valor real verificado, NO $6.000).

    Con solo estos dos contactos synthetic (no los 17 "regulares" reales,
    que no están commiteados en el repo), julio debe dar 2 eventos y
    $11.500 — confirma que la lógica multietapa+máscara funciona; el
    conteo/suma exactos sobre el dataset real completo (Count=19,
    Suma=$113.500, NO los $122.000 originalmente pedidos) se verificó por
    fuera de este test, ver la nota en clientify_business_rules.md."""
    df = pd.DataFrame([
        _fila_multietapa(
            "Clientify - Whatsapp", canal_online="paid social",
            **{"Fecha de cierre": "29/07/2026", "Valor total del proceso": "8000"},
        ),
        _fila_multietapa(
            "Clientify - Whatsapp", canal_online="paid social",
            **{
                "Fecha de cierre": "19/01/2026", "Valor total del proceso": "6000",
                "Fecha de segundo cierre": "14/07/2026", "Valor total segundo cierre": "3500",
            },
        ),
    ])
    out = calculate_redes_revenue_chart(df)
    julio = out[out["Mes_Año"] == "Julio 2026"]
    assert julio["Ingreso_Redes"].iloc[0] == 8000.0 + 3500.0


def test_revenue_from_redes_monthly_df_vacio():
    out = revenue_from_redes_monthly(pd.DataFrame())
    assert out.empty


def test_combine_ad_spend_and_revenue_outer_join_y_filtro_2025():
    gasto = pd.DataFrame([
        {"Año": 2024, "Mes_num": 12, "Mes_Año": "Diciembre 2024", "Importe": 999.0},
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Importe": 100.0},
        {"Año": 2025, "Mes_num": 2, "Mes_Año": "Febrero 2025", "Importe": 200.0},
    ])
    ingreso = pd.DataFrame([
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Ingreso_Redes": 3000.0},
        {"Año": 2025, "Mes_num": 3, "Mes_Año": "Marzo 2025", "Ingreso_Redes": 500.0},
    ])
    out = combine_ad_spend_and_revenue(gasto, ingreso)

    # Diciembre 2024 queda excluido por el filtro "desde enero 2025"
    assert "Diciembre 2024" not in out["Mes_Año"].values
    # Marzo 2025 aparece aunque no tenga gasto (outer join)
    assert "Marzo 2025" in out["Mes_Año"].values
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Concepto", "Valor"]

    enero = out[(out["Mes_Año"] == "Enero 2025") & (out["Concepto"] == "Ingreso_Redes")]
    assert enero["Valor"].iloc[0] == 3000.0

    marzo_gasto = out[(out["Mes_Año"] == "Marzo 2025") & (out["Concepto"] == "Importe")]
    assert marzo_gasto["Valor"].iloc[0] == 0.0


def test_combine_ad_spend_and_revenue_ambos_vacios():
    out = combine_ad_spend_and_revenue(pd.DataFrame(), pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Concepto", "Valor"]


def test_revenue_cuota_inicial_from_redes_monthly_suma_cuota_inicial():
    df = pd.DataFrame([
        {
            "Canal offline": "Clientify - Instagram",
            "Fecha de cierre": "01/04/2026",
            "Fecha de segundo cierre": None,
            "Cuota inicial pactada": "1.500,00",
        },
        {
            "Canal offline": "Clientify - Facebook",
            "Fecha de cierre": None,
            "Fecha de segundo cierre": "15/04/2026",
            "Cuota inicial pactada": "500,00",
        },
    ])
    out = revenue_cuota_inicial_from_redes_monthly(df)
    assert len(out) == 1
    assert out["Mes_Año"].iloc[0] == "Abril 2026"
    assert out["Ingreso_CuotaInicial"].iloc[0] == 2000.0


def test_revenue_cuota_inicial_from_redes_monthly_excluye_tiktok():
    df = pd.DataFrame([
        {
            "Canal offline": "tiktok",
            "Fecha de cierre": "01/04/2026",
            "Fecha de segundo cierre": None,
            "Cuota inicial pactada": "1000",
        },
    ])
    out = revenue_cuota_inicial_from_redes_monthly(df)
    assert out.empty


def test_revenue_cuota_inicial_from_redes_monthly_sin_columna_devuelve_vacio():
    df = pd.DataFrame([
        {"Canal offline": "Clientify - Instagram", "Fecha de cierre": "01/04/2026", "Fecha de segundo cierre": None},
    ])
    out = revenue_cuota_inicial_from_redes_monthly(df)
    assert out.empty


def test_revenue_cuota_inicial_from_redes_monthly_df_vacio():
    out = revenue_cuota_inicial_from_redes_monthly(pd.DataFrame())
    assert out.empty


def test_combine_ad_spend_revenue_and_roas_calcula_roas_por_mes():
    gasto = pd.DataFrame([
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Importe": 100.0},
        {"Año": 2025, "Mes_num": 2, "Mes_Año": "Febrero 2025", "Importe": 200.0},
    ])
    ingreso = pd.DataFrame([
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Ingreso_CuotaInicial": 300.0},
    ])
    out = combine_ad_spend_revenue_and_roas(gasto, ingreso)
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Importe", "Ingreso_CuotaInicial", "ROAS"]

    enero = out[out["Mes_Año"] == "Enero 2025"].iloc[0]
    assert enero["ROAS"] == 3.0

    febrero = out[out["Mes_Año"] == "Febrero 2025"].iloc[0]
    assert febrero["Ingreso_CuotaInicial"] == 0.0
    assert febrero["ROAS"] == 0.0


def test_combine_ad_spend_revenue_and_roas_gasto_cero_no_divide_por_cero():
    gasto = pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Importe"])
    ingreso = pd.DataFrame([
        {"Año": 2025, "Mes_num": 3, "Mes_Año": "Marzo 2025", "Ingreso_CuotaInicial": 500.0},
    ])
    out = combine_ad_spend_revenue_and_roas(gasto, ingreso)
    assert out["Importe"].iloc[0] == 0.0
    assert out["ROAS"].iloc[0] == 0.0


def test_combine_ad_spend_revenue_and_roas_filtra_desde_enero_2025():
    gasto = pd.DataFrame([
        {"Año": 2024, "Mes_num": 12, "Mes_Año": "Diciembre 2024", "Importe": 999.0},
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Importe": 100.0},
    ])
    out = combine_ad_spend_revenue_and_roas(gasto, pd.DataFrame())
    assert "Diciembre 2024" not in out["Mes_Año"].values


def test_combine_ad_spend_revenue_and_roas_ambos_vacios():
    out = combine_ad_spend_revenue_and_roas(pd.DataFrame(), pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Importe", "Ingreso_CuotaInicial", "ROAS"]


def test_combine_ad_spend_total_revenue_and_roas_suma_honorarios_por_defecto_desde_julio_2026():
    """Desde 2026-08-14, el honorario por defecto es `HONORARIOS_EQUIPO_
    MARKETING_USD` (~$3,485.44) y solo se suma a partir de julio 2026
    (`HONORARIOS_EQUIPO_DESDE_ANIO`/`_MES`) — NO retroactivamente."""
    gasto = pd.DataFrame([
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Importe": 100.0},
    ])
    ingreso = pd.DataFrame([
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Ingreso_CuotaInicial": 4200.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto, ingreso)
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Gasto_Total", "Ingreso_CuotaInicial", "ROAS"]

    julio = out.iloc[0]
    gasto_total_esperado = 100.0 + HONORARIOS_EQUIPO_MARKETING_USD
    assert julio["Gasto_Total"] == gasto_total_esperado
    assert julio["ROAS"] == 4200.0 / gasto_total_esperado


def test_combine_ad_spend_total_revenue_and_roas_sin_honorarios_antes_de_julio_2026():
    """Meses previos al corte (por defecto julio 2026) no llevan honorario —
    'Gasto_Total' es puramente el gasto en pauta, pedido 2026-08-14."""
    gasto = pd.DataFrame([
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Importe": 100.0},
        {"Año": 2026, "Mes_num": 6, "Mes_Año": "Junio 2026", "Importe": 4444.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto, pd.DataFrame())
    assert out[out["Mes_Año"] == "Enero 2025"].iloc[0]["Gasto_Total"] == 100.0
    assert out[out["Mes_Año"] == "Junio 2026"].iloc[0]["Gasto_Total"] == 4444.0


def test_combine_ad_spend_total_revenue_and_roas_honorarios_personalizados():
    gasto = pd.DataFrame([
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Importe": 100.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto, pd.DataFrame(), honorarios_fijos=500.0)
    assert out.iloc[0]["Gasto_Total"] == 600.0


def test_combine_ad_spend_total_revenue_and_roas_honorarios_solo_desde_julio_2026_con_override_de_monto():
    """El corte de fecha aplica sin importar qué monto de honorario se pase
    — un mes anterior a julio 2026 no lo lleva ni con `honorarios_fijos`
    personalizado."""
    gasto = pd.DataFrame([
        {"Año": 2026, "Mes_num": 6, "Mes_Año": "Junio 2026", "Importe": 100.0},
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Importe": 100.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto, pd.DataFrame(), honorarios_fijos=500.0)
    assert out[out["Mes_Año"] == "Junio 2026"].iloc[0]["Gasto_Total"] == 100.0
    assert out[out["Mes_Año"] == "Julio 2026"].iloc[0]["Gasto_Total"] == 600.0


def test_combine_ad_spend_total_revenue_and_roas_ejemplo_real_julio_2026():
    """Caso real del pedido 2026-08-14: $4,444 de pauta + $3,485.44 de
    honorarios del equipo en julio 2026 debe dar $7,929.44 de Gasto_Total,
    y la barra de ROAS debe recalcularse contra ese total."""
    gasto = pd.DataFrame([
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Importe": 4444.0},
    ])
    ingreso = pd.DataFrame([
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Ingreso_CuotaInicial": 10000.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto, ingreso)
    julio = out.iloc[0]
    assert round(julio["Gasto_Total"], 2) == 7929.44
    assert julio["ROAS"] == 10000.0 / julio["Gasto_Total"]


def test_combine_ad_spend_total_revenue_and_roas_mes_sin_fila_de_gasto_no_lleva_honorario():
    """Un mes que solo aparece en `ingreso_mensual` (sin fila de gasto en
    pauta ese período) no debe heredar el honorario fijo — el merge outer
    lo deja en Gasto_Total = 0, igual que si no hubiera datos de gasto."""
    gasto = pd.DataFrame([
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Importe": 100.0},
    ])
    ingreso = pd.DataFrame([
        {"Año": 2025, "Mes_num": 2, "Mes_Año": "Febrero 2025", "Ingreso_CuotaInicial": 500.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto, ingreso)
    febrero = out[out["Mes_Año"] == "Febrero 2025"].iloc[0]
    assert febrero["Gasto_Total"] == 0.0
    assert febrero["ROAS"] == 0.0


def test_combine_ad_spend_total_revenue_and_roas_filtra_desde_enero_2025():
    gasto = pd.DataFrame([
        {"Año": 2024, "Mes_num": 12, "Mes_Año": "Diciembre 2024", "Importe": 999.0},
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Importe": 100.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto, pd.DataFrame())
    assert "Diciembre 2024" not in out["Mes_Año"].values


def test_combine_ad_spend_total_revenue_and_roas_ambos_vacios():
    out = combine_ad_spend_total_revenue_and_roas(pd.DataFrame(), pd.DataFrame())
    assert out.empty
    assert list(out.columns) == ["Año", "Mes_num", "Mes_Año", "Gasto_Total", "Ingreso_CuotaInicial", "ROAS"]


# --- calculate_redes_initial_payments_chart (2026-08-13g, función aislada
# para la gráfica "Gasto total (pauta + honorarios) vs Ingresos por cuota
# inicial (redes) y ROAS") -----------------------------------------------

def test_calculate_redes_initial_payments_chart_usa_el_campo_de_cuota_correcto_por_etapa():
    """Igual que `calculate_redes_revenue_chart` pero con cuota inicial:
    cada etapa tiene su propio campo — NO debe reusarse 'Cuota inicial
    pactada' (1ra etapa) para la 2da etapa."""
    df = pd.DataFrame([
        _fila_multietapa(
            "Clientify - Whatsapp", canal_online="paid social",
            **{
                "Fecha de cierre": "19/01/2026", "Cuota inicial pactada": "1000",
                "Fecha de segundo cierre": "14/07/2026", "Cuota inicial segundo cierre": "500",
            },
        ),
    ])
    out = calculate_redes_initial_payments_chart(df)

    enero = out[out["Mes_Año"] == "Enero 2026"]
    assert enero["Ingreso_CuotaInicial"].iloc[0] == 1000.0

    julio = out[out["Mes_Año"] == "Julio 2026"]
    assert julio["Ingreso_CuotaInicial"].iloc[0] == 500.0  # NO 1000.0


def test_calculate_redes_initial_payments_chart_evalua_las_4_etapas_con_su_propia_cuota():
    df = pd.DataFrame([
        _fila_multietapa(
            "Tiktok",
            **{
                "Fecha de cierre": "01/07/2026", "Cuota inicial pactada": "100",
                "Fecha de segundo cierre": "02/07/2026", "Cuota inicial segundo cierre": "200",
                "Fecha de tercer cierre": "03/07/2026", "Cuota inicial tercer cierre": "300",
                "Fecha de 4to cierre": "04/07/2026", "Cuota inicial 4to cierre": "400",
            },
        ),
    ])
    out = calculate_redes_initial_payments_chart(df)
    assert out["Ingreso_CuotaInicial"].iloc[0] == 100.0 + 200.0 + 300.0 + 400.0


def test_calculate_redes_initial_payments_chart_incluye_organico_y_referido_redes():
    df = pd.DataFrame([
        _fila_multietapa("Organico", **{"Fecha de cierre": "01/07/2026", "Cuota inicial pactada": "1000"}),
        _fila_multietapa(
            "Referido cliente activo - Redes",
            **{"Fecha de cierre": "02/07/2026", "Cuota inicial pactada": "1000"},
        ),
    ])
    out = calculate_redes_initial_payments_chart(df)
    assert out["Ingreso_CuotaInicial"].iloc[0] == 2000.0


def test_calculate_redes_initial_payments_chart_incluye_canal_online_paid_social():
    df = pd.DataFrame([
        _fila_multietapa(
            "algun canal nuevo no listado", canal_online="paid social",
            **{"Fecha de cierre": "01/07/2026", "Cuota inicial pactada": "1000"},
        ),
    ])
    out = calculate_redes_initial_payments_chart(df)
    assert len(out) == 1
    assert out["Ingreso_CuotaInicial"].iloc[0] == 1000.0


def test_calculate_redes_initial_payments_chart_excluye_estado_inactivo():
    df = pd.DataFrame([
        _fila_multietapa(
            "Tiktok", estado="inactivo",
            **{"Fecha de cierre": "01/07/2026", "Cuota inicial pactada": "1000"},
        ),
    ])
    out = calculate_redes_initial_payments_chart(df)
    assert out.empty


def test_calculate_redes_initial_payments_chart_excluye_canal_fuera_de_redes():
    df = pd.DataFrame([
        _fila_multietapa("referido puro", **{"Fecha de cierre": "01/07/2026", "Cuota inicial pactada": "1000"}),
    ])
    out = calculate_redes_initial_payments_chart(df)
    assert out.empty


def test_calculate_redes_initial_payments_chart_df_vacio():
    out = calculate_redes_initial_payments_chart(pd.DataFrame())
    assert out.empty


def test_calculate_redes_initial_payments_chart_no_afecta_revenue_cuota_inicial_from_redes_monthly():
    """Aislamiento (punto 1 del pedido 2026-08-13g): `revenue_cuota_inicial_
    from_redes_monthly` (usada por la OTRA gráfica de ROAS, `ad_spend_roas.
    py`) sigue con su comportamiento previo (reusa la cuota del primer
    cierre para las 4 etapas) — no fue tocada."""
    df = pd.DataFrame([
        _fila_multietapa(
            "Clientify - Whatsapp", canal_online="paid social",
            **{
                "Fecha de cierre": "19/01/2026", "Cuota inicial pactada": "1000",
                "Fecha de segundo cierre": "14/07/2026", "Cuota inicial segundo cierre": "500",
            },
        ),
    ])
    out_legacy = revenue_cuota_inicial_from_redes_monthly(df)
    julio_legacy = out_legacy[out_legacy["Mes_Año"] == "Julio 2026"]
    # Comportamiento previo (no tocado): reusa "Cuota inicial pactada"
    # ($1000) para el segundo cierre en vez de $500.
    assert julio_legacy["Ingreso_CuotaInicial"].iloc[0] == 1000.0


def test_calculate_redes_initial_payments_chart_roas_se_recalcula_automaticamente():
    """Punto 5 del pedido 2026-08-13g: no hace falta tocar
    `combine_ad_spend_total_revenue_and_roas` — el ROAS se recalcula solo al
    pasarle la salida de `calculate_redes_initial_payments_chart`."""
    df = pd.DataFrame([
        _fila_multietapa(
            "Tiktok",
            **{"Fecha de cierre": "01/07/2026", "Cuota inicial pactada": "1000"},
        ),
    ])
    ingreso_mensual = calculate_redes_initial_payments_chart(df)
    gasto_mensual = pd.DataFrame([
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Importe": 500.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(gasto_mensual, ingreso_mensual, honorarios_fijos=500.0)
    julio = out[out["Mes_Año"] == "Julio 2026"].iloc[0]
    assert julio["Gasto_Total"] == 1000.0  # 500 pauta + 500 honorarios
    assert julio["Ingreso_CuotaInicial"] == 1000.0
    assert julio["ROAS"] == 1.0


# --- Desglose real de honorarios del equipo de marketing para
# ad_spend_roas.py (2026-08-13i) ---------------------------------------

def test_honorarios_equipo_marketing_usd_suma_los_4_componentes():
    """`HONORARIOS_EQUIPO_MARKETING_USD` debe ser exactamente la suma de
    Jefe CTO + Helen + Alexa (USD) + salario del usuario convertido de COP
    a USD con `USD_COP_EXCHANGE_RATE` — protege contra que alguien edite un
    componente y se le olvide que el total no se recalcula solo si se
    hardcodea en vez de sumarse."""
    salario_usuario_usd_esperado = SALARIO_USUARIO_COP / USD_COP_EXCHANGE_RATE
    assert SALARIO_USUARIO_USD == salario_usuario_usd_esperado

    total_esperado = (
        HONORARIOS_JEFE_CTO_USD + HONORARIOS_HELEN_USD + HONORARIOS_ALEXA_USD + salario_usuario_usd_esperado
    )
    assert HONORARIOS_EQUIPO_MARKETING_USD == total_esperado


def test_combine_ad_spend_total_revenue_and_roas_acepta_honorarios_equipo_como_override():
    """`combine_ad_spend_total_revenue_and_roas` es agnóstica a qué
    honorario y qué corte de fecha se le pasa — este test fija que ambos
    (`honorarios_fijos` y `honorarios_since_year`/`_month`) se pueden
    override juntos, por ejemplo para aplicar el honorario retroactivamente
    si el negocio lo pidiera. NO describe el comportamiento actual de
    `ad_spend_roas.py` (REVERTIDO 2026-08-13k: ese archivo ya no suma
    honorarios en absoluto, ver el siguiente test)."""
    gasto_mensual = pd.DataFrame([
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Importe": 100.0},
    ])
    ingreso_mensual = pd.DataFrame([
        {"Año": 2025, "Mes_num": 1, "Mes_Año": "Enero 2025", "Ingreso_CuotaInicial": 50.0},
    ])
    out = combine_ad_spend_total_revenue_and_roas(
        gasto_mensual,
        ingreso_mensual,
        honorarios_fijos=HONORARIOS_EQUIPO_MARKETING_USD,
        honorarios_since_year=2025,
        honorarios_since_month=1,
    )
    enero = out.iloc[0]
    assert enero["Gasto_Total"] == 100.0 + HONORARIOS_EQUIPO_MARKETING_USD


def test_ad_spend_roas_gasto_es_pauta_pura_sin_honorarios():
    """Comportamiento ACTUAL de `ad_spend_roas.py` (revertido 2026-08-13k):
    usa `combine_ad_spend_revenue_and_roas` (no la variante `_total_`), así
    que el "Gasto" (columna 'Importe') es exclusivamente pauta — sin sumar
    `HONORARIOS_EQUIPO_MARKETING_USD` ni `HONORARIOS_FIJOS_MENSUALES_USD`.
    El ingreso sigue usando la lógica multietapa aislada
    (`calculate_redes_initial_payments_chart`), solo el denominador del
    ROAS cambió de vuelta a gasto puro."""
    df = pd.DataFrame([
        _fila_multietapa(
            "Tiktok",
            **{"Fecha de cierre": "01/07/2026", "Cuota inicial pactada": "1000"},
        ),
    ])
    ingreso_mensual = calculate_redes_initial_payments_chart(df)
    gasto_mensual = pd.DataFrame([
        {"Año": 2026, "Mes_num": 7, "Mes_Año": "Julio 2026", "Importe": 4444.05},
    ])
    out = combine_ad_spend_revenue_and_roas(gasto_mensual, ingreso_mensual)
    julio = out[out["Mes_Año"] == "Julio 2026"].iloc[0]
    assert julio["Importe"] == 4444.05  # sin honorarios sumados
    assert julio["Ingreso_CuotaInicial"] == 1000.0
    assert julio["ROAS"] == 1000.0 / 4444.05
