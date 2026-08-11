"""Carga del reporte de Facturación/Inversión de Meta Ads (CSV o Excel)."""
from pathlib import Path
from typing import IO, Union

import pandas as pd

# Nombres canónicos que espera src/analytics/ad_spend.py, mapeados a variantes
# habituales del export de Meta Ads Manager (o de una planilla armada a mano)
# — comparación normalizada (lower + strip) para no depender de mayúsculas.
_COLUMN_ALIASES: dict[str, set[str]] = {
    "Fecha": {"fecha", "día", "dia", "date", "fecha de inicio del informe", "reporting starts"},
    "Divisa": {"divisa", "moneda", "currency"},
    "Importe": {
        "importe", "importe gastado", "importe gastado (usd)",
        "amount spent", "amount spent (usd)", "gasto", "spend",
    },
}


class AdSpendLoader:
    """Lee el reporte de inversión de Meta Ads exportado como CSV o Excel."""

    def __init__(self, file: Union[str, Path, IO[bytes]]):
        self.file = file
        self._name = getattr(file, "name", str(file))

    @property
    def source_name(self) -> str:
        return Path(self._name).name

    def load(self) -> pd.DataFrame:
        df = self._read_file()
        return self._normalize_columns(df)

    def _read_file(self) -> pd.DataFrame:
        name = str(self._name).lower()
        if hasattr(self.file, "seek"):
            self.file.seek(0)

        if name.endswith(".csv"):
            return pd.read_csv(self.file)

        if name.endswith(".xlsx") or not name.endswith(".xls"):
            try:
                return pd.read_excel(self.file, engine="calamine")
            except (ImportError, ValueError):
                if hasattr(self.file, "seek"):
                    self.file.seek(0)
        return pd.read_excel(self.file)

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Renombra columnas con nombres ligeramente distintos a los
        canónicos ("Fecha", "Divisa", "Importe") usando `_COLUMN_ALIASES`.
        Columnas que ya coinciden exactamente no se tocan."""
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]

        rename_map: dict[str, str] = {}
        for canonical, aliases in _COLUMN_ALIASES.items():
            if canonical in df.columns:
                continue
            for col in df.columns:
                if col.strip().lower() in aliases:
                    rename_map[col] = canonical
                    break
        if rename_map:
            df = df.rename(columns=rename_map)
        return df
