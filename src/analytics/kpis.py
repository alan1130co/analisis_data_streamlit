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

# Orden estricto requerido por Soluciones Migratorias (10 tarjetas principales).
KPI_DEFINITIONS_TODOS: list[KPIDefinition] = [
    KPIDefinition("creados",              "Creados del mes",              "📋", "#0F172A", "int"),
    KPIDefinition("asignados",            "Total Leads Asignados",        "🧑‍💼", "#334155", "int"),
    KPIDefinition("asignados_pauta",      "Leads Pauta Asignados",        "🎯", "#16A34A", "int"),
    KPIDefinition("leads_organico_tiktok", "Leads Orgánicos y TikTok",    "🌱", "#059669", "int"),
    KPIDefinition("calificados",          "Calificados",                  "✅", "#2563EB", "int"),
    KPIDefinition("no_calificados",       "No calificados",               "❌", "#DC2626", "int"),
    KPIDefinition("cierres_marketing",    "Cierres Pauta (M)",            "🏆", "#16A34A", "int"),
    KPIDefinition("cierres_no_pauta",     "Cierres Referidos (R)",        "🤝", "#D97706", "int"),
    KPIDefinition("cierres_adicionales",  "Cierres Adicionales",          "🔁", "#0891B2", "int"),
    KPIDefinition("total_cierres_general", "Total Cierres (M+R)",         "📊", "#0EA5E9", "int"),
]

# Fórmulas de eficiencia destacadas (no forman parte de la grilla de 10 tarjetas).
KPI_DEFINITIONS_EFICIENCIA: list[KPIDefinition] = [
    KPIDefinition("eficiencia_pauta",  "% Eficiencia de Pauta",  "📈", "#7C3AED", "percent_raw"),
    KPIDefinition("eficiencia_global", "% Eficiencia Global",    "🚀", "#EA580C", "percent_raw"),
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
