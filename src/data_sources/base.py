"""
Interfaz común para todas las fuentes de datos.

Cualquier fuente (Excel, API Clientify, base de datos, etc.) debe heredar
de ContactsDataSource y devolver un DataFrame con el mismo esquema.
"""
from abc import ABC, abstractmethod

import pandas as pd

# Columnas de fecha/texto que toda fuente debe normalizar de la misma forma
# (movido acá desde excel_loader.py para que ClientifyAPIClient reutilice
# exactamente el mismo pipeline y el esquema resultante sea idéntico sin
# importar la fuente — ver auditoría del proyecto, sección 4).
DATE_COLS = [
    "creado",
    "último contacto",
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]

TEXT_COLS = [
    "estado", "canal online", "Origen de la pauta", "propietario",
    "Motivo de no cierre", "Canal offline", "origen contacto",
]


def normalize_contacts_df(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia espacios en nombres de columna, parsea fechas y normaliza texto
    (lower+strip). Toda fuente de datos (Excel, API) debe llamar a esta misma
    función antes de devolver su DataFrame, para que `analytics/` reciba
    siempre el mismo esquema sin importar el origen.
    """
    df.columns = [c.strip() for c in df.columns]

    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    for col in TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower().replace("nan", pd.NA)

    return df


class ContactsDataSource(ABC):
    """Fuente abstracta de contactos de Clientify."""

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Carga los contactos y devuelve un DataFrame normalizado."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Nombre legible de la fuente (para mostrar en la UI)."""
        ...
