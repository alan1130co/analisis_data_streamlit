"""Configuración global de la aplicación."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

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
}

# --- Clasificación de equipo según "Canal offline" y "canal online" ---
MARKETING_OFFLINE_CHANNELS = {
    "clientify - facebook",
    "clientify - instagram",
    "clientify - whatsapp",
    "formulario de facebook - cliente potencial",
    "formulario web",
    "llamada entrante",
    "tiktok",
}

# Cualquier "Canal offline" que empiece con esto es Referidos, NO Marketing
REFERIDO_PREFIX = "referido"

# Reglas adicionales por canal online
PAID_NETWORK_CHANNELS = {"paid social"}        # Marketing
REFERRAL_ONLINE_CHANNELS = {"inbox-referral"}  # Referidos

# Para identificar pauta paga específicamente (subset de Marketing)
PAID_NETWORK_SOURCES = {"facebook", "instagram"}

# Fecha de inicio de operaciones de la empresa (año, mes)
FOUNDING_DATE = (2024, 5)
