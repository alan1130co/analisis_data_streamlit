"""
Interfaz común para todas las fuentes de datos.

Cualquier fuente (Excel, API Clientify, base de datos, etc.) debe heredar
de ContactsDataSource y devolver un DataFrame con el mismo esquema.
"""
from abc import ABC, abstractmethod

import pandas as pd


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
