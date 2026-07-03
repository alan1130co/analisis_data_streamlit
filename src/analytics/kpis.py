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
    KPIDefinition("eficiencia_pauta",     "% Eficiencia pauta",   "📈", "#7C3AED", "percent_raw"),
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

# Layout original de 8 tarjetas (revertido a pedido de Soluciones Migratorias:
# la grilla de 10 tarjetas "se descuadró" visualmente). Orgánico+TikTok va
# unificado en una sola tarjeta de control; las 2 eficiencias van dentro de
# la misma grilla, no en una sección aparte.
KPI_DEFINITIONS_TODOS: list[KPIDefinition] = [
    KPIDefinition("creados",              "Creados del mes",           "📋", "#0F172A", "int"),
    KPIDefinition("leads_pauta",          "Leads Pauta",                "🎯", "#16A34A", "int"),
    KPIDefinition("leads_organico_tiktok", "Leads Orgánicos y TikTok", "🌱", "#059669", "int"),
    KPIDefinition("calificados",          "Calificados",                "✅", "#2563EB", "int"),
    KPIDefinition("no_calificados",       "No calificados",             "❌", "#DC2626", "int"),
    KPIDefinition("total_cierres",        "Total Cierres",              "🏆", "#0EA5E9", "int"),
    KPIDefinition("eficiencia_pauta",     "% Eficiencia Pauta",         "📈", "#7C3AED", "percent_raw"),
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
