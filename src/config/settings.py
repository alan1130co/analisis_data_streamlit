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
# Nota: NO incluir "tiktok" ni "orgánico" acá — son categorías propias
# (ver TIKTOK_OFFLINE_CHANNELS / ORGANICO_OFFLINE_CHANNELS más abajo).
# Tampoco "Referido cliente activo - Redes": pese al nombre "Redes", es un
# Referido (empieza con REFERIDO_PREFIX) y debe caer en esa bolsa.
MARKETING_OFFLINE_CHANNELS = {
    "clientify - facebook",
    "clientify - instagram",
    "clientify - whatsapp",
    "formulario de facebook - cliente potencial",
    "formulario web",
    "llamada entrante",
}

# Cualquier "Canal offline" que empiece con esto es Referidos, NO Marketing
REFERIDO_PREFIX = "referido"

# Reglas adicionales por canal online
PAID_NETWORK_CHANNELS = {"paid social"}        # Marketing
REFERRAL_ONLINE_CHANNELS = {"inbox-referral"}  # Referidos

# Para identificar pauta paga específicamente (subset de Marketing)
PAID_NETWORK_SOURCES = {"facebook", "instagram"}

# --- Orgánico y TikTok (categorías propias, separadas de Pauta) ---
ORGANICO_OFFLINE_CHANNELS = {"organico", "orgánico", "facebook", "messenger", "instagram"}
ORGANICO_PAUTA_ORIGINS = {"organico", "orgánico"}

TIKTOK_OFFLINE_CHANNELS = {"tik tok", "tiktok"}
TIKTOK_PAUTA_ORIGINS = {"tik tok", "tiktok"}

# --- Validación de cierres: solo cuenta si "estado" está en este set ---
CIERRE_VALID_ESTADOS = {"activo", "activo - mora"}

# --- Asesores Comerciales: todo "propietario" cuenta como Asignado,
# excepto estas cuentas que no son comerciales (cartera/cobranza, admin) ---
NON_COMMERCIAL_OWNERS = {"cartera sm", "alan david coneo rodriguez"}

# --- César Augusto: único con este nombre en el sistema ---
CESAR_AUGUSTO_PREFIX = "cesar augusto"

# Canales que, para César Augusto, se consideran "comentarios de usuarios"
# (Messenger/Instagram) y se suman a Orgánico+TikTok sin importar el estado.
CESAR_COMENTARIOS_CHANNELS = {"messenger", "instagram"}

# Fecha de inicio de operaciones de la empresa (año, mes)
FOUNDING_DATE = (2024, 5)
