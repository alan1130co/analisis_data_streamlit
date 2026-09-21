"""
Diagnóstico: `cierres_marketing` ("Cierres de Pauta (Total)") sobre-contando
para un período dado (reportado: 42 mostrado vs 40 real en Agosto 2026).

A diferencia del diagnóstico de `creados` (scripts/diagnostic_creados_vs_
etiquetas.py, ya resuelto con un fix acotado), este campo NO pasa por
"Etiquetas" — usa exclusivamente `is_marketing()` (Canal offline/Origen de
la pauta) sobre las 4 columnas de fecha de cierre. La sospecha acá es la
CONTRARIA: falsos positivos de is_marketing() (algo que el usuario cuenta
como Referido pero el código clasifica como Pauta) o doble conteo de una
misma fila entre columnas de fecha.

Uso:
    python scripts/diagnostic_cierres_marketing.py <archivo.xls> <year> <month>

Ejemplo:
    python scripts/diagnostic_cierres_marketing.py data/raw/clientify_contactos.xls 2026 8
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.filters import filter_by_month
from src.analytics.metrics import (
    is_marketing, CLOSE_DATE_COLS, valid_closure_event_mask,
    valid_closure_estado_mask, compute_all_metrics, _safe_str,
)

pd.set_option("display.max_rows", 80)
pd.set_option("display.max_colwidth", 60)
pd.set_option("display.width", 160)

_ADICIONAL_COLS = CLOSE_DATE_COLS[1:]  # 2do, 3ro, 4to (todo menos "Fecha de cierre")


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    file_path, year, month = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    df = ExcelContactsLoader(file_path).load()
    df_period = filter_by_month(df, pd.Timestamp(year=year, month=month, day=1).date())

    mkt_mask_full = df.apply(is_marketing, axis=1)

    # --- Punto 1: desglose por columna de fecha de cierre ---
    print(f"=== Período {year}-{month:02d} — desglose por columna de cierre ===\n")
    total_mkt = 0
    total_no_mkt = 0
    eventos_pauta = []  # para el punto 2
    for col in CLOSE_DATE_COLS:
        in_month_valid = valid_closure_event_mask(df, col, year, month)
        n_total = int(in_month_valid.sum())
        n_mkt = int((in_month_valid & mkt_mask_full).sum())
        n_no_mkt = n_total - n_mkt
        total_mkt += n_mkt
        total_no_mkt += n_no_mkt
        print(f"{col:28s}: {n_total:4d} cierres válidos  |  Pauta(is_marketing=True): {n_mkt:4d}  |  Referido: {n_no_mkt:4d}")

        idx_pauta = df.index[in_month_valid & mkt_mask_full]
        for idx in idx_pauta:
            eventos_pauta.append({
                "columna": col,
                "index": idx,
                "Canal offline": _safe_str(df.at[idx, "Canal offline"]) if "Canal offline" in df.columns else "",
                "Origen de la pauta": _safe_str(df.at[idx, "Origen de la pauta"]) if "Origen de la pauta" in df.columns else "",
                "propietario": _safe_str(df.at[idx, "propietario"]) if "propietario" in df.columns else "",
            })

    print(f"\nTOTAL cierres válidos Pauta (suma de las 4 columnas) = cierres_marketing: {total_mkt}")
    print(f"TOTAL cierres válidos Referido (suma de las 4 columnas): {total_no_mkt}")

    # --- Punto 2: desglose de Canal offline / Origen de la pauta de los eventos Pauta ---
    print("\n=== PUNTO 2: Canal offline / Origen de la pauta de los eventos clasificados como Pauta ===")
    eventos_df = pd.DataFrame(eventos_pauta)
    if eventos_df.empty:
        print("(sin eventos Pauta en el período)")
    else:
        combo_counts = eventos_df.groupby(["Canal offline", "Origen de la pauta"]).size() \
            .reset_index(name="Cantidad").sort_values("Cantidad", ascending=False)
        print(combo_counts.to_string(index=False))

        print("\nDesglose por columna de fecha (para ubicar en cuál columna está el exceso):")
        print(eventos_df.groupby(["columna", "Canal offline", "Origen de la pauta"]).size()
              .reset_index(name="Cantidad").sort_values(["columna", "Cantidad"], ascending=[True, False])
              .to_string(index=False))

    # --- Punto 3: filas con fechas duplicadas entre columnas (posible doble conteo) ---
    print("\n=== PUNTO 3: filas con la MISMA fecha exacta en 2+ columnas de cierre ===")
    dup_rows = []
    for i, col_a in enumerate(CLOSE_DATE_COLS):
        for col_b in CLOSE_DATE_COLS[i + 1:]:
            dt_a = pd.to_datetime(df[col_a], errors="coerce")
            dt_b = pd.to_datetime(df[col_b], errors="coerce")
            same = dt_a.notna() & dt_b.notna() & (dt_a == dt_b)
            if same.any():
                for idx in df.index[same]:
                    dup_rows.append({
                        "index": idx, "col_a": col_a, "col_b": col_b,
                        "fecha": dt_a.loc[idx],
                        "en_periodo": bool((dt_a.loc[idx].year == year) and (dt_a.loc[idx].month == month)),
                        "is_marketing": bool(mkt_mask_full.loc[idx]),
                        "propietario": _safe_str(df.at[idx, "propietario"]) if "propietario" in df.columns else "",
                    })
    if not dup_rows:
        print("Ninguna fila tiene 2 columnas de cierre con la misma fecha exacta — descartado.")
    else:
        dup_df = pd.DataFrame(dup_rows)
        print(dup_df.to_string(index=False))
        n_dup_en_periodo_pauta = int((dup_df["en_periodo"] & dup_df["is_marketing"]).sum())
        print(f"\nDe esas, caen en el período Y son Pauta (contribuyen 2 veces a cierres_marketing "
              f"por la misma fila): {n_dup_en_periodo_pauta}")

    # --- Punto 4: identidad cierres_marketing == cierres_pauta_primer + cierres_adicionales_pauta ---
    print("\n=== PUNTO 4: identidad cierres_marketing == cierres_pauta_primer + cierres_adicionales_pauta ===")
    metrics = compute_all_metrics(df_period, df)
    suma = metrics.cierres_pauta_primer + metrics.cierres_adicionales_pauta
    print(f"cierres_marketing:                                  {metrics.cierres_marketing}")
    print(f"cierres_pauta_primer + cierres_adicionales_pauta:   {suma}  "
          f"(pauta_primer={metrics.cierres_pauta_primer}, adicionales_pauta={metrics.cierres_adicionales_pauta})")
    print("OK: la identidad se cumple." if metrics.cierres_marketing == suma
          else f"MISMATCH: diferencia de {metrics.cierres_marketing - suma}")


if __name__ == "__main__":
    main()
