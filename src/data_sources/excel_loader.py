"""Carga de contactos desde un archivo Excel exportado de Clientify."""
from pathlib import Path
from typing import IO, Union

import pandas as pd

from .base import ContactsDataSource


class ExcelContactsLoader(ContactsDataSource):
    """Lee un archivo .xls / .xlsx exportado desde Clientify."""

    def __init__(self, file: Union[str, Path, IO[bytes]], sheet_name: str = "Contactos"):
        self.file = file
        self.sheet_name = sheet_name
        self._name = getattr(file, "name", str(file))

    @property
    def source_name(self) -> str:
        return Path(self._name).name

    def load(self) -> pd.DataFrame:
        df = pd.read_excel(self.file, sheet_name=self.sheet_name)
        df = self._normalize(df)
        return df

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        """Limpia espacios en nombres de columna y parsea fechas."""
        # Quitar espacios sobrantes en los nombres de columnas
        df.columns = [c.strip() for c in df.columns]

        # Parsear columnas de fecha relevantes
        date_cols = [
            "creado",
            "último contacto",
            "Fecha de cierre",
            "Fecha de segundo cierre",
            "Fecha de tercer cierre",
            "Fecha de 4to cierre",
        ]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

        # Normalizar texto
        text_cols = [
            "estado", "canal online", "Origen de la pauta", "propietario",
            "Motivo de no cierre", "Canal offline", "origen contacto",
        ]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower().replace("nan", pd.NA)

        return df
