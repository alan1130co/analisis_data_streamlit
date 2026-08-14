"""Tests para el módulo de desglose por asesor, canal y origen."""
from datetime import datetime

import pandas as pd
import pytest

from src.analytics.breakdowns import (
    available_periods,
    cierres_por_canal,
    efficiency_by_advisor,
    pauta_vs_referidos,
)


@pytest.fixture
def leads():
    """
    5 leads que cubren: marketing/referidos, distintos asesores,
    cierres en el período, un lead viejo (2024) con 2do cierre en abril 2026.
    Strings ya normalizados (lower+strip) como haría _normalize().
    """
    return pd.DataFrame([
        # Lead 0 — Marketing, sofia, creado abril 2026, 1er cierre abril 2026
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "sofia",
            "estado": "activo",
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 5),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        # Lead 1 — Marketing, ana, creado abril 2026, sin cierre
        {
            "creado": datetime(2026, 4, 10),
            "propietario": "ana",
            "estado": "en transito",
            "canal online": "paid social",
            "Canal offline": "clientify - instagram",
            "Origen de la pauta": "instagram",
            "Motivo de no cierre": "no se logró contactar",
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        # Lead 2 — Referidos, carlos, creado abril 2026, cierre abril 2026
        {
            "creado": datetime(2026, 4, 5),
            "propietario": "carlos",
            "estado": "activo",
            "canal online": "inbox-referral",
            "Canal offline": "referido - amigo",
            "Origen de la pauta": None,
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 15),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        # Lead 3 — Marketing, sofia, creado enero 2024 (lead VIEJO),
        #           2do cierre en abril 2026
        {
            "creado": datetime(2024, 1, 15),
            "propietario": "sofia",
            "estado": "activo",
            "canal online": "paid social",
            "Canal offline": "clientify - whatsapp",
            "Origen de la pauta": "facebook",
            "Motivo de no cierre": "cliente potencial",
            "Cantidad de cierres": 2.0,
            "Fecha de cierre": datetime(2024, 1, 20),
            "Fecha de segundo cierre": datetime(2026, 4, 20),
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
        # Lead 4 — Marketing, sin propietario, creado abril 2026
        {
            "creado": datetime(2026, 4, 20),
            "propietario": None,
            "estado": "en transito",
            "canal online": "paid social",
            "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook",
            "Motivo de no cierre": None,
            "Cantidad de cierres": None,
            "Fecha de cierre": pd.NaT,
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        },
    ])


@pytest.fixture
def df_period(leads):
    """Leads creados en abril 2026 (rows 0, 1, 2, 4)."""
    return leads[leads["creado"] >= datetime(2026, 4, 1)].copy()


@pytest.fixture
def df_full(leads):
    """Dataset completo (los 5 leads)."""
    return leads.copy()


# ---------------------------------------------------------------------------
# efficiency_by_advisor
# ---------------------------------------------------------------------------

def test_efficiency_by_advisor_solo_incluye_asesores_con_leads_redes(df_period, df_full):
    """Carlos (referidos) y el lead sin propietario no deben aparecer en vista Marketing."""
    result = efficiency_by_advisor(df_period, df_full, 2026, 4, team="Marketing (pautas)", only_with_closures=False)
    asesores = set(result["Asesor"])
    assert "Carlos" not in asesores
    assert len(result) == 2
    assert {"Sofia", "Ana"} == asesores


def test_efficiency_by_advisor_only_with_closures_filtra_sin_cierres(df_period, df_full):
    """Con only_with_closures=True solo deben aparecer asesores con cierres pauta."""
    result = efficiency_by_advisor(df_period, df_full, 2026, 4, team="Marketing (pautas)", only_with_closures=True)
    asesores = set(result["Asesor"])
    assert "Ana" not in asesores   # Ana tiene 0 cierres pauta
    assert "Sofia" in asesores


def test_efficiency_by_advisor_calcula_porcentajes_correctamente(df_period, df_full):
    """
    Sofia: 1 lead pauta en el período, 1 cierre pauta en abril (lead 0, 1ra col).
    Lead 3 viejo (2024) con 2do cierre en abril NO se cuenta (solo 1ra col).
    % Efic. pauta = 100.0. Ana: 1 lead pauta, 0 cierres → 0.0.
    """
    result = efficiency_by_advisor(df_period, df_full, 2026, 4, team="Marketing (pautas)", only_with_closures=False)
    sofia = result[result["Asesor"] == "Sofia"].iloc[0]
    ana = result[result["Asesor"] == "Ana"].iloc[0]

    assert sofia["Leads pauta"] == 1
    assert sofia["Cierres pauta"] == 1
    assert sofia["% Efic. pauta"] == pytest.approx(100.0)
    assert sofia["Calificados"] == 1
    assert sofia["% Efic. s/Cal."] == pytest.approx(100.0)

    assert ana["Leads pauta"] == 1
    assert ana["Cierres pauta"] == 0
    assert ana["% Efic. pauta"] == pytest.approx(0.0)


def test_efficiency_marketing_columnas():
    """Vista Marketing devuelve solo columnas de pauta."""
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Ana",
         "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
         "Motivo de no cierre": "", "Cantidad de cierres": 1,
         "Fecha de cierre": pd.Timestamp("2026-04-05"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = efficiency_by_advisor(df, df, 2026, 4, team="Marketing (pautas)", only_with_closures=False)
    expected_cols = {"Asesor", "Leads pauta", "Cierres pauta", "% Efic. pauta", "Calificados", "% Efic. s/Cal."}
    assert set(result.columns) == expected_cols


def test_efficiency_referidos_columnas():
    """Vista Referidos devuelve solo columnas de referidos."""
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Juan",
         "Canal offline": "Referido externo", "canal online": "inbox-referral",
         "Motivo de no cierre": "", "Cantidad de cierres": 1,
         "Fecha de cierre": pd.Timestamp("2026-04-05"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = efficiency_by_advisor(df, df, 2026, 4, team="Referidos", only_with_closures=False)
    expected_cols = {"Asesor", "Leads referidos", "Cierres referidos", "% Efic. referidos", "Calificados", "% Efic. s/Cal."}
    assert set(result.columns) == expected_cols


def test_efficiency_todos_columnas():
    """Vista Todos devuelve 6 columnas: Asesor, Calificados, Cierres pauta/referidos, % Efic. pauta/global."""
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Ana",
         "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
         "Motivo de no cierre": "", "Cantidad de cierres": 1,
         "Fecha de cierre": pd.Timestamp("2026-04-05"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = efficiency_by_advisor(df, df, 2026, 4, team="Todos", only_with_closures=False)
    expected_cols = {"Asesor", "Calificados", "Cierres pauta", "Cierres referidos", "% Efic. pauta", "% Efic. global"}
    assert set(result.columns) == expected_cols


def test_efficiency_todos_calcula_eficiencia_sobre_calificados():
    """Todos: con 1 calificado (regla estricta 2026-08-12c: el 2do lead,
    motivo vacío y sin cierre, ya no califica) y 1 cierre pauta →
    % Efic. pauta = 100.0."""
    df = pd.DataFrame([
        {"creado": pd.Timestamp("2026-04-01"), "propietario": "Ana",
         "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
         "Motivo de no cierre": "", "Cantidad de cierres": 1,
         "Fecha de cierre": pd.Timestamp("2026-04-05"),
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"creado": pd.Timestamp("2026-04-02"), "propietario": "Ana",
         "Canal offline": "Clientify - Whatsapp", "canal online": "paid social",
         "Motivo de no cierre": "", "Cantidad de cierres": None,
         "Fecha de cierre": pd.NaT,
         "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    result = efficiency_by_advisor(df, df, 2026, 4, team="Todos", only_with_closures=False)
    ana = result[result["Asesor"] == "Ana"].iloc[0]
    assert ana["Calificados"] == 1
    assert ana["Cierres pauta"] == 1
    assert ana["% Efic. pauta"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# pauta_vs_referidos
# ---------------------------------------------------------------------------

def test_pauta_vs_referidos_suma_100_porciento(df_period, df_full):
    """Pauta + Referidos debe sumar exactamente 100 % de los cierres del mes."""
    result = pauta_vs_referidos(df_period, df_full, 2026, 4)
    total_pct = result["Porcentaje"].sum()
    assert total_pct == pytest.approx(100.0)

    # Cierres válidos en abril, sumando las 4 columnas de fecha de cierre:
    #   Lead 0 (mkt, sofia): Fecha de cierre April 5 → Pauta
    #   Lead 2 (ref, carlos): Fecha de cierre April 15 → Referidos
    #   Lead 3 (old 2024, mkt): Fecha de segundo cierre April 20 → Pauta
    pauta = result[result["Origen"] == "Pauta"].iloc[0]
    ref = result[result["Origen"] == "Referidos"].iloc[0]
    assert pauta["Cantidad"] == 2
    assert ref["Cantidad"] == 1


def test_pauta_vs_referidos_sin_fuga_coincide_con_total_cierres_general(df_period, df_full):
    """Pauta + Referidos del gráfico debe coincidir EXACTAMENTE con
    total_cierres_general del KPI (ninguna categoría — Organico/TikTok incluidos —
    debe quedar fuera de ambos buckets)."""
    from src.analytics.metrics import compute_all_metrics

    result = pauta_vs_referidos(df_period, df_full, 2026, 4)
    total_grafico = int(result["Cantidad"].sum())
    total_kpi = compute_all_metrics(df_period, df_full).total_cierres_general
    assert total_grafico == total_kpi, (
        f"Fuga detectada: gráfico={total_grafico}, KPI total_cierres_general={total_kpi}"
    )


# ---------------------------------------------------------------------------
# cierres_por_canal
# ---------------------------------------------------------------------------

def test_cierres_por_canal_team_marketing_excluye_referidos(df_period, df_full):
    """Con team='Marketing (pautas)', el canal 'Referido - Amigo' no debe aparecer."""
    result = cierres_por_canal(df_period, df_full, 2026, 4, team="Marketing (pautas)")
    assert "Referido - Amigo" not in result["Canal"].values


def test_cierres_por_canal_suma_las_4_columnas(df_period, df_full):
    """
    Lead 3 fue creado en enero 2024 con Canal offline 'clientify - whatsapp'.
    Su Fecha de cierre (1ra) es enero 2024, pero su 2do cierre cae en abril 2026
    y ahora SÍ se cuenta (se suman las 4 columnas de fecha de cierre).
    """
    result = cierres_por_canal(df_period, df_full, 2026, 4, team="Marketing (pautas)")
    assert "Clientify - Facebook" in result["Canal"].values
    assert "Clientify - Whatsapp" in result["Canal"].values
    cantidad = result.loc[result["Canal"] == "Clientify - Whatsapp", "Cantidad"].iloc[0]
    assert cantidad == 1


def test_cierres_por_canal_team_referidos_solo_referidos(df_period, df_full):
    """Con team='Referidos', solo aparecen canales referido y 'Sin Canal (Referido)'."""
    result = cierres_por_canal(df_period, df_full, 2026, 4, team="Referidos")
    for canal in result["Canal"]:
        assert canal.lower().startswith("referido") or canal.lower().startswith("sin canal")


def test_cierres_por_canal_team_todos_incluye_todo(df_period, df_full):
    """Con team='Todos', la suma de cierres debe ser mayor o igual que con Marketing."""
    result_all = cierres_por_canal(df_period, df_full, 2026, 4, team="Todos")
    result_mkt = cierres_por_canal(df_period, df_full, 2026, 4, team="Marketing (pautas)")
    assert result_all["Cantidad"].sum() >= result_mkt["Cantidad"].sum()


def test_cierres_por_canal_team_todos_suma_total_general(df_period, df_full):
    """team='Todos' debe sumar exactamente el mismo total que total_cierres_general
    (todas las fuentes), ya que total_cierres del KPI excluye Referidos/TikTok."""
    from src.analytics.metrics import compute_all_metrics
    expected = compute_all_metrics(df_period, df_full).total_cierres_general
    canal_total = int(cierres_por_canal(df_period, df_full, 2026, 4, team="Todos")["Cantidad"].sum())
    assert canal_total == expected, f"cierres_por_canal={canal_total}, KPI={expected}"


def test_cierres_sin_canal_se_agrupan_como_referido():
    """Un cierre con Canal offline vacío aparece en 'Referidos' y 'Todos', no en 'Marketing'."""
    from datetime import datetime
    df = pd.DataFrame([
        {
            "creado": datetime(2026, 4, 1),
            "propietario": "sofia",
            "estado": "activo",
            "canal online": "inbox",
            "Canal offline": None,          # sin canal → referido
            "Origen de la pauta": None,
            "Motivo de no cierre": None,
            "Cantidad de cierres": 1.0,
            "Fecha de cierre": datetime(2026, 4, 10),
            "Fecha de segundo cierre": pd.NaT,
            "Fecha de tercer cierre": pd.NaT,
            "Fecha de 4to cierre": pd.NaT,
        }
    ])
    result_todos = cierres_por_canal(df, df, 2026, 4, team="Todos")
    result_ref = cierres_por_canal(df, df, 2026, 4, team="Referidos")
    result_mkt = cierres_por_canal(df, df, 2026, 4, team="Marketing (pautas)")

    assert result_todos["Cantidad"].sum() == 1
    assert result_ref["Cantidad"].sum() == 1
    assert result_mkt.empty or result_mkt["Cantidad"].sum() == 0


def test_cierres_por_canal_backwards_compat(df_period, df_full):
    """El parámetro legado only_marketing=True debe funcionar igual que team='Marketing'."""
    result_new = cierres_por_canal(df_period, df_full, 2026, 4, team="Marketing (pautas)")
    result_old = cierres_por_canal(df_period, df_full, 2026, 4, only_marketing=True)
    assert result_new.equals(result_old)


def test_cierres_por_canal_y_pauta_vs_referidos_usan_periodo_explicito():
    """Bug de desincronización de fechas: estas funciones ya NO deben adivinar
    el período desde df_period['creado'] (con fallback a pd.Timestamp.now()) —
    deben usar exactamente el (year, month) que reciben como argumento,
    incluso si difiere del mes en que se crearon los leads de df_period."""
    df_period = pd.DataFrame([{
        # Lead ASIGNADO en abril (para que df_period no esté vacío)...
        "creado": datetime(2026, 4, 1), "propietario": "sofia", "estado": "activo",
        "canal online": "paid social", "Canal offline": "clientify - facebook",
        "Origen de la pauta": "facebook", "Motivo de no cierre": "cliente potencial",
        "Cantidad de cierres": None, "Fecha de cierre": pd.NaT,
        "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
    }])
    df_full = pd.DataFrame([
        df_period.iloc[0].to_dict(),
        {
            # ...pero su CIERRE ocurre en julio, un período distinto al de
            # creación. Si estas funciones siguieran infiriendo el período
            # desde df_period (todo abril), este cierre de julio nunca se
            # contaría al pedir explícitamente year=2026, month=7.
            "creado": datetime(2026, 3, 5), "propietario": "sofia", "estado": "activo",
            "canal online": "paid social", "Canal offline": "clientify - facebook",
            "Origen de la pauta": "facebook", "Motivo de no cierre": None,
            "Cantidad de cierres": 1.0, "Fecha de cierre": datetime(2026, 7, 10),
            "Fecha de segundo cierre": pd.NaT, "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT,
        },
    ])

    canal_julio = cierres_por_canal(df_period, df_full, 2026, 7, team="Todos")
    assert int(canal_julio["Cantidad"].sum()) == 1
    canal_abril = cierres_por_canal(df_period, df_full, 2026, 4, team="Todos")
    assert int(canal_abril["Cantidad"].sum()) == 0

    pvr_julio = pauta_vs_referidos(df_period, df_full, 2026, 7)
    assert int(pvr_julio["Cantidad"].sum()) == 1
    pvr_abril = pauta_vs_referidos(df_period, df_full, 2026, 4)
    assert int(pvr_abril["Cantidad"].sum()) == 0


# --- available_periods (2026-08-14: alimenta el selector propio de
# "Pauta vs Referidos" y "Cierres por canal", src/ui/period_selector.py) ---

def test_available_periods_lista_meses_con_al_menos_un_cierre():
    df = pd.DataFrame([
        {"Fecha de cierre": datetime(2026, 4, 1), "Fecha de segundo cierre": pd.NaT,
         "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
        {"Fecha de cierre": pd.NaT, "Fecha de segundo cierre": datetime(2026, 7, 15),
         "Fecha de tercer cierre": pd.NaT, "Fecha de 4to cierre": pd.NaT},
    ])
    assert available_periods(df) == [(2026, 7), (2026, 4)]


def test_available_periods_ordena_de_mas_reciente_a_mas_antiguo():
    df = pd.DataFrame([
        {"Fecha de cierre": datetime(2025, 1, 1)},
        {"Fecha de cierre": datetime(2026, 6, 1)},
        {"Fecha de cierre": datetime(2025, 12, 1)},
    ])
    assert available_periods(df) == [(2026, 6), (2025, 12), (2025, 1)]


def test_available_periods_df_vacio_devuelve_lista_vacia():
    assert available_periods(pd.DataFrame()) == []


def test_available_periods_sin_columnas_de_cierre_devuelve_lista_vacia():
    df = pd.DataFrame([{"propietario": "sofia"}])
    assert available_periods(df) == []
