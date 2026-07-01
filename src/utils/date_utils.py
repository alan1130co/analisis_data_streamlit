"""Helpers para fechas."""
from datetime import date, datetime

MONTHS_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def month_label_es(d: date | datetime) -> str:
    """Devuelve un label tipo 'abril 2026'."""
    return f"{MONTHS_ES[d.month]} {d.year}"
