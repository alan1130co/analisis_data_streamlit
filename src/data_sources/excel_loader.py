"""Carga de contactos desde un archivo Excel exportado de Clientify."""
from pathlib import Path
from typing import IO, Union

import pandas as pd

from .base import ContactsDataSource, normalize_contacts_df


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
        df = self._read_excel()
        df = normalize_contacts_df(df)
        return df

    def _read_excel(self) -> pd.DataFrame:
        """Lee el Excel con el motor más rápido disponible.

        `python-calamine` (Rust) parsea .xlsx varias veces más rápido que
        openpyxl, que es puro Python y es el cuello de botella dominante al
        cargar un archivo de varios MB. Si el paquete no está instalado o el
        archivo es .xls (no soportado por calamine), cae a los motores por
        defecto de pandas (openpyxl / xlrd) sin cambiar ningún resultado.
        """
        name = str(self._name).lower()
        if name.endswith(".xlsx") or not name.endswith(".xls"):
            try:
                if hasattr(self.file, "seek"):
                    self.file.seek(0)
                return pd.read_excel(self.file, sheet_name=self.sheet_name, engine="calamine")
            except (ImportError, ValueError):
                if hasattr(self.file, "seek"):
                    self.file.seek(0)
        return pd.read_excel(self.file, sheet_name=self.sheet_name)
