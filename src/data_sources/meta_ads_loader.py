import pandas as pd


class MetaAdsLoader:
    """Carga y normaliza el CSV de Meta Ads Manager."""

    NUMERIC_COLS = [
        "Importe gastado (USD)", "Impresiones", "Alcance",
        "Clics en el enlace", "Nuevos contactos de mensajes",
        "Resultados", "CPM (coste por 1000 impresiones) (USD)",
    ]

    def __init__(self, source):
        """source puede ser un path string o un UploadedFile de Streamlit."""
        self.source = source

    def load(self) -> pd.DataFrame:
        df = pd.read_csv(self.source, encoding="utf-8")
        df.columns = [c.strip() for c in df.columns]

        for col in ["Inicio del informe", "Fin del informe"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        for col in self.NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
