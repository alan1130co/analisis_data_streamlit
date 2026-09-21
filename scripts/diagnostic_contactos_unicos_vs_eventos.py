"""
Diagnóstico: ¿la discrepancia 78 (app, suma de EVENTOS de cierre across las 4
columnas de fecha) vs 76 (Clientify, filtro directo por "Fecha de cierre")
se explica porque Clientify cuenta CONTACTOS ÚNICOS con al menos 1 cierre
válido en el mes, mientras la app suma columnas por separado (un mismo
contacto con 1er Y 2do cierre ambos en agosto cuenta 2 veces)?

Uso:
    python scripts/diagnostic_contactos_unicos_vs_eventos.py <archivo.xls> <year> <month>

Ejemplo:
    python scripts/diagnostic_contactos_unicos_vs_eventos.py data/raw/clientify_contactos.xls 2026 8
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.filters import filter_by_month
from src.analytics.metrics import (
    CLOSE_DATE_COLS, valid_closure_event_mask, compute_all_metrics, _safe_str,
)

pd.set_option("display.max_rows", 80)
pd.set_option("display.max_colwidth", 60)
pd.set_option("display.width", 160)


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    file_path, year, month = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    df = ExcelContactsLoader(file_path).load()
    df_period = filter_by_month(df, pd.Timestamp(year=year, month=month, day=1).date())

    print(f"=== Período {year}-{month:02d} ===\n")

    # Máscara de validez (estado != inactivo, en el mes) por columna.
    col_masks = {col: valid_closure_event_mask(df, col, year, month) for col in CLOSE_DATE_COLS}

    # Cuántas columnas válidas tiene cada fila (0 a 4).
    n_cols_validos = pd.Series(0, index=df.index)
    for col, m in col_masks.items():
        n_cols_validos = n_cols_validos + m.astype(int)

    # --- Punto 1: contactos únicos con al menos 1 columna válida en el mes ---
    tiene_al_menos_1 = n_cols_validos >= 1
    n_contactos_unicos = int(tiene_al_menos_1.sum())
    print(f"--- PUNTO 1: contactos únicos con >=1 cierre válido en {year}-{month:02d} ---")
    print(f"Contactos únicos: {n_contactos_unicos}\n")

    # --- Punto 2: contactos con 2+ columnas válidas en el mismo mes ---
    tiene_2_o_mas = n_cols_validos >= 2
    n_multi = int(tiene_2_o_mas.sum())
    print(f"--- PUNTO 2: contactos con 2+ columnas de cierre válidas dentro de {year}-{month:02d} ---")
    print(f"Contactos con doble/triple/cuádruple conteo potencial: {n_multi}\n")

    if n_multi:
        rows = []
        for idx in df.index[tiene_2_o_mas]:
            fila = {
                "index": idx,
                "propietario": _safe_str(df.at[idx, "propietario"]) if "propietario" in df.columns else "",
                "Canal offline": _safe_str(df.at[idx, "Canal offline"]) if "Canal offline" in df.columns else "",
                "n_columnas_validas": int(n_cols_validos.loc[idx]),
            }
            for col in CLOSE_DATE_COLS:
                if col_masks[col].loc[idx]:
                    fecha = pd.to_datetime(df.at[idx, col], errors="coerce")
                    fila[col] = fecha.strftime("%Y-%m-%d") if pd.notna(fecha) else ""
                else:
                    fila[col] = ""
            rows.append(fila)
        print(pd.DataFrame(rows).to_string(index=False))
        print()

    # --- Punto 3: eventos totales vs contactos únicos ---
    total_eventos = int(sum(m.sum() for m in col_masks.values()))
    diff = total_eventos - n_contactos_unicos
    exceso_por_multi = int((n_cols_validos[tiene_2_o_mas] - 1).sum())  # columnas "extra" más allá de la 1ra
    print("--- PUNTO 3: comparación eventos vs contactos únicos ---")
    print(f"Total EVENTOS (suma de las 4 columnas, lo que ya calculamos = cierres_marketing + cierres_referidos): {total_eventos}")
    print(f"Total CONTACTOS ÚNICOS (>=1 columna válida): {n_contactos_unicos}")
    print(f"Diferencia (eventos - contactos únicos): {diff}")
    print(f"Columnas 'extra' de los contactos con 2+ columnas válidas (debería coincidir con la diferencia de arriba): {exceso_por_multi}")
    print("OK: la diferencia se explica exactamente por el doble conteo de contactos multi-columna." if diff == exceso_por_multi
          else "MISMATCH: la diferencia NO coincide con el exceso por multi-columna — revisar manualmente.")

    # Referencia cruzada con el número ya confirmado por compute_all_metrics.
    metrics = compute_all_metrics(df_period, df)
    total_app = metrics.cierres_marketing + metrics.cierres_referidos
    print(f"\n(Referencia: cierres_marketing + cierres_referidos vía compute_all_metrics = {total_app}, "
          f"debería coincidir con el total de EVENTOS de arriba: {total_eventos})")

    # --- Punto 4: conclusión ---
    print("\n--- PUNTO 4: conclusión ---")
    if n_contactos_unicos == 76:
        print(f"Contactos únicos = {n_contactos_unicos} == 76: CONFIRMA la hipótesis de conteo por "
              "contacto único vs eventos por columna.")
    else:
        print(f"Contactos únicos = {n_contactos_unicos} (no 76) — la hipótesis de 'contacto único vs "
              "evento' NO explica por sí sola la discrepancia con Clientify. Revisar otro ángulo "
              "(ej. criterio de validez de estado distinto en Clientify, o filtro de fecha distinto).")


if __name__ == "__main__":
    main()
