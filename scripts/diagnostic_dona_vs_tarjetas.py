"""
Diagnóstico: la dona "Pauta vs Referidos" (breakdowns.pauta_vs_referidos)
muestra un total distinto (reportado: 76) al de las tarjetas "Cierres de
Pauta (Total)"/"Cierres de Referidos (Total)" (metrics.cierres_marketing/
cierres_referidos, reportado: 78) para el MISMO período.

Por lectura de código, ambas funciones usan exactamente el mismo predicado
(`is_marketing`), las mismas 4 columnas de fecha de cierre y el mismo
criterio de validez de estado — deberían dar el mismo número para el mismo
(year, month) y el mismo DataFrame. Este script fuerza el MISMO (year,
month) explícito para las 2 rutas de cálculo (nada de selectores de UI
independientes) y, si aun así difieren, imprime el desglose evento-por-
evento exacto de qué cierres están en una ruta y no en la otra.

Uso:
    python scripts/diagnostic_dona_vs_tarjetas.py <archivo.xls> <year> <month>

Ejemplo:
    python scripts/diagnostic_dona_vs_tarjetas.py data/raw/clientify_contactos.xls 2026 8
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.filters import filter_by_month
from src.analytics.breakdowns import pauta_vs_referidos
from src.analytics.metrics import (
    is_marketing, is_organico, is_tiktok, CLOSE_DATE_COLS,
    valid_closure_estado_mask, valid_closure_event_mask,
    compute_all_metrics, _safe_str,
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

    print(f"=== Forzando (year, month) = ({year}, {month}) EXPLÍCITO en ambas rutas ===\n")

    # --- Ruta 1: dona (breakdowns.pauta_vs_referidos) ---
    dona = pauta_vs_referidos(df, df, year, month)
    dona_pauta = int(dona.loc[dona["Origen"] == "Pauta", "Cantidad"].iloc[0])
    dona_ref = int(dona.loc[dona["Origen"] == "Referidos", "Cantidad"].iloc[0])
    print(f"DONA (pauta_vs_referidos):        Pauta={dona_pauta}  Referidos={dona_ref}  Total={dona_pauta + dona_ref}")

    # --- Ruta 2: tarjetas (metrics.compute_all_metrics) ---
    metrics = compute_all_metrics(df_period, df)
    print(f"TARJETAS (cierres_marketing/referidos): Pauta={metrics.cierres_marketing}  "
          f"Referidos={metrics.cierres_referidos}  Total={metrics.cierres_marketing + metrics.cierres_referidos}\n")

    if dona_pauta == metrics.cierres_marketing and dona_ref == metrics.cierres_referidos:
        print("Con el MISMO (year, month) explícito, AMBAS rutas dan el mismo número.")
        print("=> El desfase real (76 vs 78 en la app) es casi seguro un DESAJUSTE DE PERÍODO")
        print("   entre el selector propio de la dona y el selector global — no una diferencia")
        print("   de clasificación en el código. Revisa qué (year, month) exacto tiene")
        print("   seleccionado cada selectbox en la UI cuando ves 76 vs 78.")
        return

    print("¡DIFERENCIA CONFIRMADA incluso con el mismo (year, month)! Desglosando evento por evento...\n")

    # --- Desglose evento-por-evento para las 2 rutas, replicado independientemente ---
    mkt_mask = df.apply(is_marketing, axis=1)
    active = valid_closure_estado_mask(df)

    dona_eventos = set()
    for col in CLOSE_DATE_COLS:
        dt = pd.to_datetime(df[col], errors="coerce")
        in_month = (dt.dt.year == year) & (dt.dt.month == month) & active
        for idx in df.index[in_month & mkt_mask]:
            dona_eventos.add((idx, col))

    tarjetas_eventos = set()
    for col in CLOSE_DATE_COLS:
        m = valid_closure_event_mask(df, col, year, month)
        for idx in df.index[m & mkt_mask]:
            tarjetas_eventos.add((idx, col))

    solo_en_tarjetas = tarjetas_eventos - dona_eventos
    solo_en_dona = dona_eventos - tarjetas_eventos

    def _mostrar(eventos, titulo):
        print(f"--- {titulo} ({len(eventos)}) ---")
        if not eventos:
            print("(ninguno)")
            return
        rows = []
        for idx, col in sorted(eventos, key=lambda t: (t[1], t[0])):
            rows.append({
                "index": idx, "columna": col,
                "Canal offline": _safe_str(df.at[idx, "Canal offline"]) if "Canal offline" in df.columns else "",
                "Origen de la pauta": _safe_str(df.at[idx, "Origen de la pauta"]) if "Origen de la pauta" in df.columns else "",
                "estado": _safe_str(df.at[idx, "estado"]) if "estado" in df.columns else "",
                "propietario": _safe_str(df.at[idx, "propietario"]) if "propietario" in df.columns else "",
            })
        print(pd.DataFrame(rows).to_string(index=False))

    _mostrar(solo_en_tarjetas, "Cierres Pauta contados en TARJETAS pero NO en la DONA")
    _mostrar(solo_en_dona, "Cierres Pauta contados en la DONA pero NO en TARJETAS")


if __name__ == "__main__":
    main()
