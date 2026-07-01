import pandas as pd

NUMERIC_COLS = [
    "Importe gastado (USD)", "Resultados", "Coste por resultados",
    "Impresiones", "Alcance", "Clics en el enlace",
    "CPM (coste por 1000 impresiones) (USD)", "Frecuencia",
]


class MetaSetsLoader:
    """Carga el CSV de Conjuntos de anuncios de Meta Ads Manager."""

    def __init__(self, source):
        self.source = source

    def load(self) -> pd.DataFrame:
        df = pd.read_csv(self.source, encoding="utf-8")
        df.columns = [c.strip() for c in df.columns]

        for col in ["Inicio del informe", "Fin del informe", "Inicio", "Fin"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        for col in NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
