"""
Diagnóstico de cierres de abril 2026.

Imprime cierre por cierre con propietario, Canal offline, fecha, columna y equipo.
Muestra agrupado por Canal offline con clasificación.
Resalta cierres con Cantidad >= 2, propietario vacío, o canales con "Redes".
Termina con resumen total/pauta/referidos vs esperados (34/19/15).

Uso:
    python scripts/diagnostic_april_2026.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.metrics import compute_all_metrics, is_marketing
from src.analytics.filters import filter_by_month

EXPECTED_TOTAL = 34
EXPECTED_MKT = 19
EXPECTED_REF = 15

CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]

pd.set_option("display.max_rows", 300)
pd.set_option("display.max_colwidth", 45)
pd.set_option("display.width", 160)


def main() -> None:
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    files = sorted(raw_dir.glob("*.xls*"))
    if not files:
        print(f"ERROR: No hay archivos en {raw_dir}")
        sys.exit(1)

    archivo = files[-1]
    print(f"Archivo: {archivo.name}\n")

    df = ExcelContactsLoader(str(archivo)).load()
    df_april = filter_by_month(df, date(2026, 4, 1))

    # Clasificar todos los leads del dataset completo
    df = df.copy()
    df["_mkt"] = df.apply(is_marketing, axis=1)
    df["Equipo"] = df["_mkt"].map({True: "PAUTA", False: "REFERIDO"})

    # Recopilar cada evento de cierre en abril
    rows = []
    for col in CLOSE_COLS:
        if col not in df.columns:
            continue
        fechas = pd.to_datetime(df[col], errors="coerce")
        mask = (fechas.dt.year == 2026) & (fechas.dt.month == 4)
        for idx in df.index[mask]:
            row = df.loc[idx]
            cantidad = row.get("Cantidad de cierres", None)
            try:
                cantidad_num = float(cantidad) if pd.notna(cantidad) else 0.0
            except (TypeError, ValueError):
                cantidad_num = 0.0

            id_lead = row.get("id", row.get("Id", idx))
            prop = row.get("propietario", "")
            canal_off = row.get("Canal offline", "")
            canal_on = row.get("canal online", "")

            flags = []
            if cantidad_num >= 2:
                flags.append("MULTI-CIERRE")
            if not prop or str(prop).strip().lower() in {"nan", "none", ""}:
                flags.append("SIN-PROPIETARIO")
            if "redes" in str(canal_off).lower():
                flags.append("CONTIENE-REDES")

            rows.append({
                "id_lead": id_lead,
                "propietario": prop,
                "Canal offline": canal_off,
                "canal online": canal_on,
                "columna": col,
                "fecha": fechas[idx].date() if pd.notna(fechas[idx]) else None,
                "Cantidad de cierres": cantidad,
                "is_marketing": row["_mkt"],
                "Equipo": row["Equipo"],
                "flags": " | ".join(flags) if flags else "",
            })

    df_det = pd.DataFrame(rows)

    # --- SECCIÓN 1: cierre por cierre ---
    sep = "=" * 120
    print(sep)
    print(f"DETALLE CIERRE POR CIERRE — abril 2026 ({len(df_det)} eventos)")
    print(sep)
    if df_det.empty:
        print("(ningún cierre encontrado)")
    else:
        print(df_det.sort_values("fecha").to_string(index=False))

    # --- SECCIÓN 2: agrupado por Canal offline ---
    print(f"\n{sep}")
    print("AGRUPADO POR Canal offline + Equipo")
    print(sep)
    if not df_det.empty:
        ag = (
            df_det.groupby(["Canal offline", "Equipo"], dropna=False)
            .size()
            .reset_index(name="cierres")
            .sort_values(["Equipo", "cierres"], ascending=[True, False])
        )
        print(ag.to_string(index=False))

    # --- SECCIÓN 3: casos especiales ---
    print(f"\n{sep}")
    print("CASOS ESPECIALES")
    print(sep)
    if not df_det.empty:
        multi = df_det[df_det["flags"].str.contains("MULTI-CIERRE", na=False)]
        print(f"\nMulti-cierre (Cantidad >= 2): {len(multi)}")
        if not multi.empty:
            print(multi[["id_lead", "propietario", "Canal offline", "Cantidad de cierres", "Equipo"]].to_string(index=False))

        sin_prop = df_det[df_det["flags"].str.contains("SIN-PROPIETARIO", na=False)]
        print(f"\nSin propietario: {len(sin_prop)}")
        if not sin_prop.empty:
            print(sin_prop[["id_lead", "Canal offline", "fecha", "Equipo"]].to_string(index=False))

        con_redes = df_det[df_det["flags"].str.contains("CONTIENE-REDES", na=False)]
        print(f"\nCanal offline contiene 'Redes': {len(con_redes)}")
        if not con_redes.empty:
            print(con_redes[["id_lead", "propietario", "Canal offline", "Equipo", "fecha"]].to_string(index=False))

    # --- SECCIÓN 4: resumen vs esperado ---
    metrics = compute_all_metrics(df_april, df)
    print(f"\n{sep}")
    print("RESUMEN FINAL vs ESPERADO")
    print(sep)
    checks = [
        ("Total cierres", metrics.total_cierres, EXPECTED_TOTAL),
        ("Cierres PAUTA (Marketing)", metrics.cierres_marketing, EXPECTED_MKT),
        ("Cierres REFERIDOS", metrics.cierres_referidos, EXPECTED_REF),
    ]
    all_ok = True
    for label, real, esp in checks:
        estado = "OK   " if real == esp else "FALLA"
        if real != esp:
            all_ok = False
        print(f"  [{estado}] {label}: obtenido={real}  esperado={esp}")
    print()
    if all_ok:
        print("Todos los totales cuadran.")
    else:
        print("DIFERENCIAS DETECTADAS — revisá el detalle arriba.")


if __name__ == "__main__":
    main()
