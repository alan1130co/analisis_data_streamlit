"""Configuración global de la aplicación."""
import os
from pathlib import Path

# Cargar .env desde la raíz del proyecto
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except Exception:
    # En Streamlit Cloud no hay .env, se usan st.secrets
    pass

# --- App ---
APP_TITLE: str = os.getenv("APP_TITLE", "Clientify Analyzer")
APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "America/Bogota")

# --- Clientify API ---
CLIENTIFY_API_TOKEN: str = os.getenv("CLIENTIFY_API_TOKEN", "")
CLIENTIFY_BASE_URL: str = os.getenv("CLIENTIFY_BASE_URL", "https://api.clientify.net/v1")

# --- Rutas ---
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# --- Calificación del lead (columna "Motivo de no cierre") ---
# Strings ya normalizados (lower + strip), igual que hace _normalize() en el loader.
QUALIFIED_MOTIVES = {
    "cliente potencial",
    "dejó de contestar",
    "manifestó no tener interes",
    "manifestó no tener dinero",
    "no tenia dinero",
    "prefiere oficina local en su estado",
    "cliente de seguimiento",
}

UNQUALIFIED_MOTIVES = {
    "no se logró contactar",
    "no contestó",
    "su caso no aplicaba",
    "no aplica",
    "ya tenia abogado, solo consulta",
    "se acogió a una mejor propuesta económica",
    "tenia orden de deportación",
    "otra",
    "otra (notificar para agregar en las opciones)",
    "por definir",
    "consulta gratis",
}

# --- Clasificación de equipo según "Canal offline" y "canal online" ---
# Regla de negocio 2026-07-03e: TikTok, Orgánico y "redes" (en cualquier
# variante, incluso "Referido...Redes") pasaron a contar como PAUTA — ver
# is_marketing() en metrics.py. Este set queda como catch-all adicional
# para canales de marketing que no encajan en TikTok/Orgánico/redes.
MARKETING_OFFLINE_CHANNELS = {
    "clientify - facebook",
    "clientify - instagram",
    "clientify - whatsapp",
    "formulario de facebook - cliente potencial",
    "formulario web",
    "llamada entrante",
}

# Cualquier "Canal offline" que empiece con esto es Referido PURO — salvo que
# además contenga "redes" (ver PAUTA_REDES_TERM / is_marketing), en cuyo caso
# es Pauta pese al prefijo "referido".
REFERIDO_PREFIX = "referido"

# Reglas adicionales por canal online
PAID_NETWORK_CHANNELS = {"paid social"}        # Marketing
REFERRAL_ONLINE_CHANNELS = {"inbox-referral"}  # Referidos

# Para identificar pauta paga específicamente (subset de Marketing)
PAID_NETWORK_SOURCES = {"facebook", "instagram"}

# Si "Canal offline" contiene este término (substring), es Pauta SIN
# EXCEPCIÓN, incluso si además dice "referido" (p.ej. "Referido cliente
# activo - Redes"). Se evalúa ANTES que el check de REFERIDO_PREFIX.
PAUTA_REDES_TERM = "redes"

# "Cualquier canal de redes sociales" (Facebook, Instagram, WhatsApp,
# Messenger, etc.) cuenta como Pauta — chequeado por substring/contains
# sobre "Canal offline", no por igualdad exacta, para cubrir variantes.
SOCIAL_CHANNEL_TERMS = {"facebook", "instagram", "whatsapp", "messenger"}

# Cualquier "Canal offline" que contenga "llamada" (Llamada Entrante,
# Llamada Telefónica, Llamada Saliente, etc.) cuenta como Pauta — por
# substring, no por igualdad exacta contra "llamada entrante" únicamente.
PAUTA_LLAMADA_TERM = "llamada"

# --- Orgánico y TikTok (categorías propias, separadas de Pauta) ---
# Solo los términos EXACTOS "Orgánico"/"TikTok" en Canal offline (u Origen de
# la pauta, como substring) cuentan para la bolsa general, PARA LEADS QUE NO
# SON DE CÉSAR AUGUSTO. "facebook", "messenger" e "instagram" fueron
# removidos de acá: sumaban de más leads de CUALQUIER asesor con esos
# canales a la bolsa Orgánico/TikTok. Todo lead de César cuenta aparte, sin
# importar el canal (ver CESAR_AUGUSTO_PREFIX / is_cesar_augusto).
ORGANICO_OFFLINE_CHANNELS = {"organico", "orgánico"}
ORGANICO_PAUTA_ORIGINS = {"organico", "orgánico"}

TIKTOK_OFFLINE_CHANNELS = {"tik tok", "tiktok"}
TIKTOK_PAUTA_ORIGINS = {"tik tok", "tiktok"}

# --- Validación de cierres: un cierre es válido SALVO que "estado" sea
# exactamente "inactivo" (contrato caído / dinero devuelto). Regla cambiada
# el 2026-07-03: antes exigía "estado" == activo/activo-mora (lista blanca),
# lo que descartaba re-cierres y cierres en estados intermedios válidos.
# Ahora es lista negra: todo cuenta excepto "inactivo".
CIERRE_INVALID_ESTADOS = {"inactivo"}

# --- Asesores Comerciales: todo "propietario" cuenta como Asignado,
# excepto estas cuentas que no son comerciales (cartera/cobranza, admin) ---
NON_COMMERCIAL_OWNERS = {"cartera sm", "alan david coneo rodriguez"}

# --- César Augusto: único con este nombre en el sistema ---
# Regla 2026-07-03h: TODO lead cuyo propietario sea César cuenta para la
# bolsa Orgánico+TikTok (Suma 1), sin importar canal, origen de contacto ni
# estado — ver is_cesar_augusto / compute_all_metrics en metrics.py.
CESAR_AUGUSTO_PREFIX = "cesar augusto"

# Fecha de inicio de operaciones de la empresa (año, mes)
FOUNDING_DATE = (2024, 5)

# --- Honorarios fijos mensuales (USD) — desglose histórico 850 + 650 + 500
# = 2,000 USD/mes. SUPERADO 2026-08-14: ya no es el valor por defecto de
# `combine_ad_spend_total_revenue_and_roas` (ver HONORARIOS_EQUIPO_MARKETING_
# USD y HONORARIOS_EQUIPO_DESDE_* abajo). Se conserva solo como referencia
# histórica; no queda ninguna llamada en el código que lo use.
HONORARIOS_FIJOS_MENSUALES_USD = 850 + 650 + 500

# --- Honorarios/sueldos reales del equipo de marketing (USD). Desde
# 2026-08-14 es el valor por DEFECTO de `combine_ad_spend_total_revenue_and_
# roas`, usado por `ad_spend_total_roas.py` (gráfica "Gasto total (pauta +
# honorarios) vs Ingresos por cuota inicial (redes) y ROAS") — pero SOLO se
# suma al gasto desde HONORARIOS_EQUIPO_DESDE_ANIO/MES en adelante (ver
# abajo); antes de esa fecha el gasto total de esa gráfica es pauta pura,
# igual que `ad_spend_roas.py`.
HONORARIOS_JEFE_CTO_USD = 1000.0
HONORARIOS_HELEN_USD = 800.0
HONORARIOS_ALEXA_USD = 800.0

# Salario del usuario, en COP (moneda local) — se convierte a USD con
# `USD_COP_EXCHANGE_RATE` antes de sumarse al resto del equipo.
SALARIO_USUARIO_COP = 2_765_489.26

# Tasa de cambio COP -> USD. Constante configurable a mano: este proyecto no
# tiene una fuente de datos de forex en vivo, así que hay que actualizar
# este número manualmente si la tasa real cambia. Valor actualizado
# 2026-08-13 con la TRM oficial de Colombia (Banco de la República) de ese
# mismo día: 1 USD = 3.123,28 COP. Si la tasa real cambia, actualizar solo
# este número — el resto del cálculo (SALARIO_USUARIO_USD,
# HONORARIOS_EQUIPO_MARKETING_USD) se recalcula solo.
USD_COP_EXCHANGE_RATE = 3123.28

SALARIO_USUARIO_USD = SALARIO_USUARIO_COP / USD_COP_EXCHANGE_RATE

# Total de honorarios + sueldo del equipo de marketing, ya convertido a USD.
HONORARIOS_EQUIPO_MARKETING_USD = (
    HONORARIOS_JEFE_CTO_USD + HONORARIOS_HELEN_USD + HONORARIOS_ALEXA_USD + SALARIO_USUARIO_USD
)

# Mes desde el cual `combine_ad_spend_total_revenue_and_roas` suma
# HONORARIOS_EQUIPO_MARKETING_USD al gasto en pauta (pedido 2026-08-14: el
# honorario del equipo empezó a contarse recién en julio 2026, no debe
# aplicarse retroactivamente al histórico enero 2025 - junio 2026).
HONORARIOS_EQUIPO_DESDE_ANIO = 2026
HONORARIOS_EQUIPO_DESDE_MES = 7
