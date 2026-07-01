import pandas as pd
from typing import List


TEL_COL = "¿cuál_es_tu_número_de_teléfono?"
NOMBRE_COL = "¿cuál_es_tu_nombre_completo?"

class MetaCPLoader:
    """Carga y combina múltiples CSVs de Clientes Potenciales de Meta.

    Cada archivo corresponde a UN video/anuncio y viene en UTF-16.
    """

    def __init__(self, sources: list):
        """sources: lista de UploadedFile (Streamlit) o paths."""
        self.sources = sources if isinstance(sources, list) else [sources]

    def load(self) -> pd.DataFrame:
        dfs = []
        for src in self.sources:
            df = self._read_single(src)
            if df is not None and not df.empty:
                dfs.append(df)
        if not dfs:
            return pd.DataFrame()
        combined = pd.concat(dfs, ignore_index=True)
        # Deduplicar por id (mismo CP en dos archivos)
        if "id" in combined.columns:
            combined = combined.drop_duplicates(subset=["id"], keep="first")
        # Normalizar teléfono y email para el cruce
        combined["_tel_norm"] = combined[TEL_COL].apply(normalize_phone) if TEL_COL in combined.columns else ""
        combined["_email_norm"] = combined["email"].apply(normalize_email) if "email" in combined.columns else ""
        return combined.reset_index(drop=True)

    def _read_single(self, source):
        """Intenta leer con UTF-16 primero (que es lo que exporta Meta), fallback a UTF-8."""
        for enc in ["utf-16", "utf-16-le", "utf-8", "latin1"]:
            try:
                # Si es UploadedFile, reiniciar el cursor
                if hasattr(source, "seek"):
                    source.seek(0)
                df = pd.read_csv(source, encoding=enc, sep=None, engine="python")
                df.columns = [c.strip() for c in df.columns]
                if "id" in df.columns or "ad_name" in df.columns:
                    return df
            except Exception:
                continue
        return None


def normalize_phone(phone) -> str:
    """Normaliza un teléfono para cruce: solo dígitos, sin +1 si son 11 dígitos."""
    if pd.isna(phone):
        return ""
    s = str(phone)
    # Solo dígitos
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return ""
    # Quitar código de país USA/Canadá si son 11 dígitos y empiezan con 1
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def normalize_email(email) -> str:
    """Normaliza email para cruce: minúsculas + trim."""
    if pd.isna(email):
        return ""
    return str(email).strip().lower()
