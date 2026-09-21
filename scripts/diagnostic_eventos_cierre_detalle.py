"""
Diagnóstico (SOLO LECTURA, sin fixes): lista TODOS los eventos de cierre
individuales que componen "Cierres de Pauta (Total)" y "Cierres de
Referidos (Total)" para un período dado, contacto por contacto, para
comparar manualmente contra Clientify.

Recorre las 4 columnas de fecha de cierre (Fecha de cierre / segundo /
tercer / 4to) y, para cada evento válido (estado != "inactivo") que cae en
el mes pedido, imprime: contacto, propietario, cuál columna de cierre es,
fecha exacta, Canal offline, Origen de la pauta, resultado de is_marketing()
(Pauta/Referido) e índice de fila para poder rastrearlo.

No implementa ningún fix — es puramente informativo.

Uso:
    python scripts/diagnostic_eventos_cierre_detalle.py <archivo.xls> <year> <month>

Ejemplo:
    python scripts/diagnostic_eventos_cierre_detalle.py data/raw/clientify_contactos.xls 2026 8
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.metrics import (
    is_marketing, CLOSE_DATE_COLS, valid_closure_event_mask, _safe_str,
)

pd.set_option("display.max_rows", 200)
pd.set_option("display.max_colwidth", 40)
pd.set_option("display.width", 220)

# Etiqueta legible para cada columna de fecha de cierre, en el mismo orden
# que CLOSE_DATE_COLS (1ra/2da/3ra/4ta).
COL_LABELS = {
    "Fecha de cierre": "1ra (Fecha de cierre)",
    "Fecha de segundo cierre": "2da (Fecha de segundo cierre)",
    "Fecha de tercer cierre": "3ra (Fecha de tercer cierre)",
    "Fecha de 4to cierre": "4ta (Fecha de 4to cierre)",
}

# Columnas candidatas para identificar al contacto, en orden de preferencia.
# El export de Clientify no siempre trae la misma columna de nombre, así que
# se prueba una lista y se usa la primera que exista en el archivo real.
NAME_CANDIDATES = ["nombre", "Nombre", "Contacto", "contacto", "Nombre completo", "email", "Email"]


def _contact_label(df: pd.DataFrame, idx) -> str:
    for col in NAME_CANDIDATES:
        if col in df.columns:
            val = _safe_str(df.at[idx, col])
            if val and val.lower() != "nan":
                return val
    return f"(sin nombre, index={idx})"


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    file_path, year, month = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    df = ExcelContactsLoader(file_path).load()

    name_col_used = next((c for c in NAME_CANDIDATES if c in df.columns), None)
    print(f"Columna usada para identificar contacto: {name_col_used!r}\n")

    mkt_mask_full = df.apply(is_marketing, axis=1)

    eventos = []
    for col in CLOSE_DATE_COLS:
        valid_in_month = valid_closure_event_mask(df, col, year, month)
        for idx in df.index[valid_in_month]:
            fecha = df.at[idx, col]
            canal_off = _safe_str(df.at[idx, "Canal offline"]) if "Canal offline" in df.columns else ""
            origen_pauta = _safe_str(df.at[idx, "Origen de la pauta"]) if "Origen de la pauta" in df.columns else ""
            propietario = _safe_str(df.at[idx, "propietario"]) if "propietario" in df.columns else ""
            es_pauta = bool(mkt_mask_full.loc[idx])
            eventos.append({
                "index": idx,
                "contacto": _contact_label(df, idx),
                "propietario": propietario,
                "columna_cierre": COL_LABELS.get(col, col),
                "fecha": fecha,
                "canal_offline": canal_off.strip().lower() if canal_off else canal_off,
                "origen_pauta": origen_pauta,
                "clasificacion": "Pauta" if es_pauta else "Referido",
                "_es_pauta": es_pauta,
            })

    eventos_df = pd.DataFrame(eventos)
    if eventos_df.empty:
        print(f"No se encontraron eventos de cierre válidos en {year}-{month:02d}.")
        return

    display_cols = [
        "index", "contacto", "propietario", "columna_cierre", "fecha",
        "canal_offline", "origen_pauta", "clasificacion",
    ]

    for label, flag in (("PAUTA", True), ("REFERIDO", False)):
        bloque = eventos_df[eventos_df["_es_pauta"] == flag].sort_values(
            ["columna_cierre", "fecha"]
        )
        print(f"\n{'=' * 100}")
        print(f"BLOQUE: {label} ({len(bloque)} eventos)")
        print("=" * 100)
        print(bloque[display_cols].to_string(index=False))
        print(f"\nSubtotal {label}: {len(bloque)}")

        print(f"\n--- Resumen por 'Canal offline' dentro de {label} ---")
        resumen = bloque.groupby("canal_offline", dropna=False).size() \
            .reset_index(name="cantidad").sort_values("cantidad", ascending=False)
        print(resumen.to_string(index=False))

    total_pauta = int((eventos_df["_es_pauta"]).sum())
    total_referido = int((~eventos_df["_es_pauta"]).sum())
    print(f"\n{'=' * 100}")
    print(f"TOTAL Pauta:    {total_pauta}")
    print(f"TOTAL Referido: {total_referido}")
    print(f"TOTAL general:  {total_pauta + total_referido}")


if __name__ == "__main__":
    main()
