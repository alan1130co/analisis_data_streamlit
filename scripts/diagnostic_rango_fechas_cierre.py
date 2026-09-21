"""
Diagnóstico (SOLO LECTURA, sin fixes): prueba si la discrepancia
Pauta=42 (nuestro sistema) vs Pauta=40 (Clientify real) para Agosto 2026 se
explica por un desfase de RANGO DE FECHAS / zona horaria en el límite del
mes (Excel en UTC vs Clientify mostrando hora local, p.ej. Colombia UTC-5),
en vez de por una mala clasificación is_marketing().

Calcula cierres_marketing (Pauta) y cierres_referidos (Referido) con 3
rangos de fecha distintos sobre las 4 columnas de fecha de cierre:

  1. Rango ACTUAL (mes calendario estricto): 2026-08-01 a 2026-08-31.
  2. Rango alternativo A: 2026-07-31 a 2026-08-31 (un día antes del inicio).
  3. Rango alternativo B: 2026-08-01 a 2026-09-01 (un día después del final).

Compara cada uno contra el real de Clientify (Pauta=40, Referido=36,
Total=76) y, si ninguno matchea exacto, lista qué filas entran/salen al
cambiar de rango (contacto, fecha, columna, Canal offline, Origen de la
pauta, clasificación), para ver si coincide con los 2 casos ya detectados
("José Luis" 10/08 y "Claudia Marcela" 27/08, "Referido cliente activo -
Redes") o si son eventos distintos.

No implementa ningún fix — es puramente informativo.

Uso:
    python scripts/diagnostic_rango_fechas_cierre.py <archivo.xls> <year> <month>

Ejemplo:
    python scripts/diagnostic_rango_fechas_cierre.py data/raw/clientify_contactos.xls 2026 8
"""
import calendar
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.metrics import (
    is_marketing, CLOSE_DATE_COLS, valid_closure_estado_mask, _safe_str,
)

pd.set_option("display.max_rows", 200)
pd.set_option("display.max_colwidth", 40)
pd.set_option("display.width", 220)

CLIENTIFY_REAL = {"pauta": 40, "referido": 36, "total": 76}

COL_LABELS = {
    "Fecha de cierre": "1ra (Fecha de cierre)",
    "Fecha de segundo cierre": "2da (Fecha de segundo cierre)",
    "Fecha de tercer cierre": "3ra (Fecha de tercer cierre)",
    "Fecha de 4to cierre": "4ta (Fecha de 4to cierre)",
}

NAME_CANDIDATES = ["nombre", "Nombre", "Contacto", "contacto", "Nombre completo", "email", "Email"]


def _contact_label(df: pd.DataFrame, idx) -> str:
    for col in NAME_CANDIDATES:
        if col in df.columns:
            val = _safe_str(df.at[idx, col])
            if val and val.lower() != "nan":
                return val
    return f"(sin nombre, index={idx})"


def _events_in_range(df, mkt_mask_full, valid_mask, start, end) -> pd.DataFrame:
    """Devuelve un DataFrame con un evento por fila (index, col) cuya fecha
    cae en [start, end] INCLUSIVE (ambos límites incluidos) y cuyo estado es
    válido (estado != 'inactivo'). No filtra por mes calendario — el
    llamador decide el rango exacto."""
    rows = []
    for col in CLOSE_DATE_COLS:
        if col not in df.columns:
            continue
        fechas = pd.to_datetime(df[col], errors="coerce")
        in_range = fechas.notna() & (fechas >= start) & (fechas <= end)
        mask = in_range & valid_mask
        for idx in df.index[mask]:
            es_pauta = bool(mkt_mask_full.loc[idx])
            rows.append({
                "index": idx,
                "col": col,
                "columna_cierre": COL_LABELS.get(col, col),
                "contacto": _contact_label(df, idx),
                "propietario": _safe_str(df.at[idx, "propietario"]) if "propietario" in df.columns else "",
                "fecha": fechas.loc[idx],
                "canal_offline": _safe_str(df.at[idx, "Canal offline"]).strip().lower() if "Canal offline" in df.columns else "",
                "origen_pauta": _safe_str(df.at[idx, "Origen de la pauta"]) if "Origen de la pauta" in df.columns else "",
                "clasificacion": "Pauta" if es_pauta else "Referido",
                "_es_pauta": es_pauta,
            })
    return pd.DataFrame(rows)


def _summarize(label: str, events: pd.DataFrame) -> tuple[int, int]:
    pauta = int(events["_es_pauta"].sum()) if not events.empty else 0
    referido = int((~events["_es_pauta"]).sum()) if not events.empty else 0
    total = pauta + referido
    diff_pauta = pauta - CLIENTIFY_REAL["pauta"]
    diff_referido = referido - CLIENTIFY_REAL["referido"]
    diff_total = total - CLIENTIFY_REAL["total"]
    match = "MATCH EXACTO" if (pauta, referido) == (CLIENTIFY_REAL["pauta"], CLIENTIFY_REAL["referido"]) else "no matchea"
    print(f"\n--- {label} ---")
    print(f"Pauta:    {pauta:4d}  (Clientify real: {CLIENTIFY_REAL['pauta']}, diff: {diff_pauta:+d})")
    print(f"Referido: {referido:4d}  (Clientify real: {CLIENTIFY_REAL['referido']}, diff: {diff_referido:+d})")
    print(f"Total:    {total:4d}  (Clientify real: {CLIENTIFY_REAL['total']}, diff: {diff_total:+d})")
    print(f"=> {match}")
    return pauta, referido


def _diff_events(label: str, baseline: pd.DataFrame, alterno: pd.DataFrame) -> None:
    key_cols = ["index", "col"]
    base_keys = set(map(tuple, baseline[key_cols].values)) if not baseline.empty else set()
    alt_keys = set(map(tuple, alterno[key_cols].values)) if not alterno.empty else set()

    added_keys = alt_keys - base_keys
    removed_keys = base_keys - alt_keys

    print(f"\n=== Diferencias: {label} vs rango actual ===")
    if not added_keys and not removed_keys:
        print("(sin diferencias — mismos eventos exactamente)")
        return

    display_cols = ["index", "contacto", "propietario", "columna_cierre", "fecha", "canal_offline", "origen_pauta", "clasificacion"]

    if added_keys:
        added = alterno[alterno.apply(lambda r: (r["index"], r["col"]) in added_keys, axis=1)]
        print(f"\nEntran ({len(added)}) al usar este rango (no estaban en el rango actual):")
        print(added[display_cols].to_string(index=False))
    else:
        print("\nEntran: ninguno")

    if removed_keys:
        removed = baseline[baseline.apply(lambda r: (r["index"], r["col"]) in removed_keys, axis=1)]
        print(f"\nSalen ({len(removed)}) al usar este rango (estaban en el rango actual, ya no):")
        print(removed[display_cols].to_string(index=False))
    else:
        print("\nSalen: ninguno")


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    file_path, year, month = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    df = ExcelContactsLoader(file_path).load()

    mkt_mask_full = df.apply(is_marketing, axis=1)
    valid_mask = valid_closure_estado_mask(df)

    # --- Rango 1: mes calendario estricto (el actual, sin cambios) ---
    first_day = pd.Timestamp(year=year, month=month, day=1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = pd.Timestamp(year=year, month=month, day=last_day_num)
    # Límite superior INCLUSIVE hasta el final del día (23:59:59.999...) para
    # no perder eventos con hora != 00:00:00 el último día del mes.
    last_day_end = last_day + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

    # --- Rango 2: un día antes del inicio (sospecha: TZ corre eventos de
    # fin de julio hacia agosto, o viceversa) ---
    day_before = first_day - pd.Timedelta(days=1)

    # --- Rango 3: un día después del final ---
    day_after_end = last_day + pd.Timedelta(days=1)
    day_after_end_end = day_after_end + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

    print(f"Rango ACTUAL:        {first_day.date()}  a  {last_day.date()} (inclusive, fin de día)")
    print(f"Rango alternativo A: {day_before.date()}  a  {last_day.date()} (inclusive, fin de día) — 1 día antes del inicio")
    print(f"Rango alternativo B: {first_day.date()}  a  {day_after_end.date()} (inclusive, fin de día) — 1 día después del final")

    events_actual = _events_in_range(df, mkt_mask_full, valid_mask, first_day, last_day_end)
    events_a = _events_in_range(df, mkt_mask_full, valid_mask, day_before, last_day_end)
    events_b = _events_in_range(df, mkt_mask_full, valid_mask, first_day, day_after_end_end)

    _summarize("Rango ACTUAL (mes calendario estricto)", events_actual)
    _summarize("Rango alternativo A (31 jul - 31 ago)", events_a)
    _summarize("Rango alternativo B (1 ago - 1 sep)", events_b)

    _diff_events("Rango alternativo A (31 jul - 31 ago)", events_actual, events_a)
    _diff_events("Rango alternativo B (1 ago - 1 sep)", events_actual, events_b)

    # --- Chequeo puntual: ¿aparecen los 2 casos ya identificados manualmente? ---
    print(f"\n{'=' * 100}")
    print("Chequeo puntual: José Luis (10/08) y Claudia Marcela (27/08), ambos 'Referido cliente activo - Redes'")
    print("=" * 100)
    for needle in ["jose luis", "josé luis", "claudia marcela"]:
        for events_label, events in (("actual", events_actual), ("alternativo A", events_a), ("alternativo B", events_b)):
            if events.empty:
                continue
            match = events[events["contacto"].str.lower().str.contains(needle, na=False)]
            if not match.empty:
                print(f"\n'{needle}' encontrado en rango {events_label}:")
                print(match[["index", "contacto", "columna_cierre", "fecha", "canal_offline", "clasificacion"]].to_string(index=False))


if __name__ == "__main__":
    main()
