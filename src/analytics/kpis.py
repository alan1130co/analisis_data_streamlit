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

# Layout de 11 tarjetas (2026-09-03c: reemplaza las 3 tarjetas de cierres
# desglosados por orden de cierre — Pauta(M)/Referidos(R)/Adicionales — por
# 4 tarjetas desglosadas por canal Y por primer-cierre-vs-re-cierre. Sigue
# el layout de 10 tarjetas de 2026-07-03c, que a su vez había reemplazado la
# tarjeta "Leads Pauta" por 3 bolsas de cierres desglosadas ANTES del total.
# Orgánico+TikTok sigue unificado en una sola tarjeta de control; las 2
# eficiencias van dentro de la misma grilla. No incluye "Leads Pauta" ni
# ninguna tarjeta de "Líderes Pauta" (esa nunca existió en el código; el
# reporte visual la confundía con la tarjeta verde "Leads Pauta").
#
# Los cierres se muestran en 5 tarjetas consecutivas, en este orden:
#   Cierres de Pauta (Total) -> Cierres de Referidos (Total) ->
#   Re-cierres de Pauta -> Re-cierres de Referidos -> Total Cierres.
# Los 2 "Total" son cierres_marketing/cierres_referidos (suman las 4
# columnas de fecha de cierre, no solo la 1ra); los 2 "Re-cierres" son
# cierres_adicionales_pauta/cierres_adicionales_referido (solo 2da/3ra/4ta
# columna). "Total Cierres" sigue usando total_cierres_estricto =
# cierres_pauta_primer + cierres_referido_primer + cierres_adicionales —
# esos 3 campos NO se tocaron (siguen existiendo en Metrics, usados también
# por KPI_DEFINITIONS_MARKETING/REFERIDOS), solo dejaron de tener tarjeta
# propia en ESTE layout. La identidad Cierres de Pauta (Total) ==
# cierres_pauta_primer + Re-cierres de Pauta se cumple por construcción
# (mismas 4 columnas, mismo mkt_mask_full, solo agrupadas distinto) —
# ver test_total_cierres_estricto_es_la_suma_de_las_3_tarjetas_de_cierre.
#
# 2026-07-03i: "% Eficiencia Pauta" se renombró a "% Eficiencia Real"
# (campo eficiencia_real) y cambió de fórmula: Cierres de Pauta*100 /
# Calificados del mes. "% Eficiencia Bruta" (campo eficiencia_global, el
# nombre interno del campo NO se tocó — ver metrics.py Metrics.eficiencia_global
# — solo el label visible cambió en 2026-09-04) también cambió: Cierres de
# Pauta*100 / Creados del mes. Ambas usan "Cierres de Pauta" (cierres_marketing)
# como numerador — antes eficiencia_global usaba el total de TODOS los cierres
# (Pauta+Referidos).
#
# OJO (2026-09-04): existe además un campo `eficiencia_bruta` en Metrics, con
# fórmula DISTINTA (no se muestra en ninguna tarjeta hoy) — no confundir ese
# campo con el label "% Eficiencia Bruta" de acá abajo, que apunta a
# `eficiencia_global`. Decisión explícita del usuario pese al choque de nombre.
KPI_DEFINITIONS_TODOS: list[KPIDefinition] = [
    # 2026-09-08c: label renombrado de "Creados del mes" a "Leads de Pauta y
    # Orgánico" — refleja mejor lo que el campo `creados` mide desde
    # 2026-09-08 (Pauta+Orgánico, excluye Referido puro y César); el nombre
    # interno del campo (`Metrics.creados`) NO se tocó, solo el texto visible.
    KPIDefinition("creados",              "Leads de Pauta y Orgánico",  "📋", "#0F172A", "int"),
    KPIDefinition("leads_organico_tiktok", "Leads Orgánicos y TikTok", "🌱", "#059669", "int"),
    KPIDefinition("calificados",          "Calificados",                "✅", "#2563EB", "int"),
    KPIDefinition("no_calificados",       "No calificados",             "❌", "#DC2626", "int"),
    KPIDefinition("cierres_marketing",    "Cierres de Pauta (Total)",   "🎯", "#16A34A", "int"),
    KPIDefinition("cierres_referidos",    "Cierres de Referidos (Total)", "🤝", "#D97706", "int"),
    KPIDefinition("cierres_adicionales_pauta", "Re-cierres de Pauta",  "🔁", "#0891B2", "int"),
    KPIDefinition("cierres_adicionales_referido", "Re-cierres de Referidos", "🔁", "#0891B2", "int"),
    KPIDefinition("total_cierres_estricto", "Total Cierres",            "🏆", "#0EA5E9", "int"),
    KPIDefinition("eficiencia_real",      "% Eficiencia Real",          "📈", "#7C3AED", "percent_raw"),
    KPIDefinition("eficiencia_global",    "% Eficiencia Bruta",         "📊", "#EA580C", "percent_raw"),
    KPIDefinition("leads_clientify_whatsapp", "Leads Clientify WhatsApp", "💬", "#0284C7", "int"),
    KPIDefinition("leads_formulario_facebook_cp", "Leads Formulario Facebook-CP", "📝", "#7C3AED", "int"),
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
