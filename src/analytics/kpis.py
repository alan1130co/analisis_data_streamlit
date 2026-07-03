"""Definiciones (labels, iconos, formato) para mostrar los KPIs."""
from dataclasses import dataclass


@dataclass(frozen=True)
class KPIDefinition:
    key: str
    label: str
    icon: str          # emoji
    color: str         # hex CSS color
    format: str        # "int" | "percent"


KPI_DEFINITIONS_MARKETING: list[KPIDefinition] = [
    KPIDefinition("creados",              "Creados del mes",      "📋", "#0F172A", "int"),
    KPIDefinition("creados_pauta",        "Creados por pauta",    "📅", "#16A34A", "int"),
    KPIDefinition("calificados_pauta",    "Calificados",          "✅", "#2563EB", "int"),
    KPIDefinition("no_calificados_pauta", "No calificados",       "❌", "#DC2626", "int"),
    KPIDefinition("cierres_pauta_primer",  "Cierres pauta",        "🎯", "#16A34A", "int"),
    KPIDefinition("cierres_adicionales_pauta", "Cierres adicionales",  "🔁", "#0891B2", "int"),
    KPIDefinition("eficiencia_real",      "% Eficiencia Real",    "📈", "#7C3AED", "percent_raw"),
    KPIDefinition("eficiencia_total",     "% Eficiencia global",  "📊", "#EA580C", "percent"),
]

KPI_DEFINITIONS_REFERIDOS: list[KPIDefinition] = [
    KPIDefinition("creados",                 "Creados del mes",        "📋", "#0F172A", "int"),
    KPIDefinition("creados_referido",        "Creados por referido",   "📅", "#D97706", "int"),
    KPIDefinition("calificados_referido",    "Calificados",            "✅", "#2563EB", "int"),
    KPIDefinition("no_calificados_referido", "No calificados",         "❌", "#DC2626", "int"),
    KPIDefinition("cierres_referido_primer", "Cierres referidos",      "🤝", "#D97706", "int"),
    KPIDefinition("cierres_adicionales_referido", "Cierres adicionales",    "🔁", "#0891B2", "int"),
    KPIDefinition("eficiencia_referido",     "% Eficiencia referidos", "📈", "#7C3AED", "percent"),
    KPIDefinition("eficiencia_total",        "% Eficiencia global",    "📊", "#EA580C", "percent"),
]

# Layout de 10 tarjetas (2026-07-03c: reemplaza la tarjeta "Leads Pauta" por
# las 3 bolsas de cierres que pide el negocio, desglosadas ANTES del total).
# Orgánico+TikTok sigue unificado en una sola tarjeta de control; las 2
# eficiencias van dentro de la misma grilla. No incluye "Leads Pauta" ni
# ninguna tarjeta de "Líderes Pauta" (esa nunca existió en el código; el
# reporte visual la confundía con la tarjeta verde "Leads Pauta").
#
# Los cierres se muestran en 4 tarjetas consecutivas, en este orden:
#   Cierres de Pauta (M) -> Cierres de Referidos (R) -> Cierres Adicionales
#   (re-cierres 2do/3ro/4to, todos los canales) -> Total Cierres.
# "Total Cierres" usa total_cierres_estricto = suma ESTRICTA de las 3
# tarjetas anteriores (no un total calculado por otro camino), para que
# nunca vuelva a desincronizarse de lo que el usuario ve en pantalla.
#
# 2026-07-03i: "% Eficiencia Pauta" se renombró a "% Eficiencia Real"
# (campo eficiencia_real) y cambió de fórmula: Cierres de Pauta*100 /
# Calificados del mes. "% Eficiencia Global" (campo eficiencia_global, sin
# renombrar) también cambió: Cierres de Pauta*100 / Creados del mes. Ambas
# usan "Cierres de Pauta" (cierres_marketing) como numerador — antes
# eficiencia_global usaba el total de TODOS los cierres (Pauta+Referidos).
KPI_DEFINITIONS_TODOS: list[KPIDefinition] = [
    KPIDefinition("creados",              "Creados del mes",           "📋", "#0F172A", "int"),
    KPIDefinition("leads_organico_tiktok", "Leads Orgánicos y TikTok", "🌱", "#059669", "int"),
    KPIDefinition("calificados",          "Calificados",                "✅", "#2563EB", "int"),
    KPIDefinition("no_calificados",       "No calificados",             "❌", "#DC2626", "int"),
    KPIDefinition("cierres_pauta_primer", "Cierres de Pauta (M)",       "🎯", "#16A34A", "int"),
    KPIDefinition("cierres_referido_primer", "Cierres de Referidos (R)", "🤝", "#D97706", "int"),
    KPIDefinition("cierres_adicionales",  "Cierres Adicionales (Re-cierres)", "🔁", "#0891B2", "int"),
    KPIDefinition("total_cierres_estricto", "Total Cierres",            "🏆", "#0EA5E9", "int"),
    KPIDefinition("eficiencia_real",      "% Eficiencia Real",          "📈", "#7C3AED", "percent_raw"),
    KPIDefinition("eficiencia_global",    "% Eficiencia Global",        "📊", "#EA580C", "percent_raw"),
]


def get_kpi_definitions(team: str) -> list[KPIDefinition]:
    """Devuelve la lista de KPIs correspondiente al equipo seleccionado."""
    if team == "Marketing (pautas)":
        return KPI_DEFINITIONS_MARKETING
    if team == "Referidos":
        return KPI_DEFINITIONS_REFERIDOS
    return KPI_DEFINITIONS_TODOS


# Backwards-compat alias
KPI_DEFINITIONS = KPI_DEFINITIONS_TODOS
