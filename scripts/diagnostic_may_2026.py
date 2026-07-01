"""
Diagnóstico de cierres de mayo 2026.

Hipótesis a verificar:
  - ¿El sistema cuenta 35 o 41 cierres en mayo?
  - ¿Hay leads que aparecen en MÁS de una columna de cierre dentro del mes?
  - ¿Hay cierres con propietario vacío?
  - ¿Hay cierres con Canal offline = "Orgánico"?
  - ¿Hay leads con Cantidad >= 2 siendo sobre-contados?

Uso:
    python scripts/diagnostic_may_2026.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.metrics import compute_all_metrics, is_marketing
from src.analytics.filters import filter_by_month

YEAR = 2026
MONTH = 5
EXPECTED_TOTAL = 35
EXPECTED_MKT = 21
EXPECTED_REF = 14

CLOSE_COLS = [
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
]
COL_LABEL = {
    "Fecha de cierre": "1ra",
    "Fecha de segundo cierre": "2da",
    "Fecha de tercer cierre": "3ra",
    "Fecha de 4to cierre": "4ta",
}

pd.set_option("display.max_rows", 400)
pd.set_option("display.max_colwidth", 35)
pd.set_option("display.width", 200)


def main() -> None:
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    files = sorted(raw_dir.glob("*.xls*"))
    if not files:
        print(f"ERROR: No hay archivos .xls/.xlsx en {raw_dir}")
        print("Copiá el Excel de Clientify en data/raw/ y volvé a correr el script.")
        sys.exit(1)

    archivo = files[-1]
    print(f"Archivo: {archivo.name}\n")

    df = ExcelContactsLoader(str(archivo)).load()
    df = df.copy()
    df["_mkt"] = df.apply(is_marketing, axis=1)
    df["Equipo"] = df["_mkt"].map({True: "PAUTA", False: "REFERIDO"})

    df_mayo = filter_by_month(df, date(YEAR, MONTH, 1))

    # -------------------------------------------------------------------------
    # Recopilar cada evento de cierre en mayo — UNA FILA POR CIERRE
    # -------------------------------------------------------------------------
    rows = []
    for col in CLOSE_COLS:
        if col not in df.columns:
            continue
        fechas = pd.to_datetime(df[col], errors="coerce")
        mask = (fechas.dt.year == YEAR) & (fechas.dt.month == MONTH)
        for idx in df.index[mask]:
            row = df.loc[idx]

            cantidad = row.get("Cantidad de cierres", None)
            try:
                cantidad_num = float(cantidad) if pd.notna(cantidad) else 0.0
            except (TypeError, ValueError):
                cantidad_num = 0.0

            id_lead = row.get("id", row.get("Id", idx))
            prop = row.get("propietario", "")
            canal_off = str(row.get("Canal offline", "") or "")
            canal_on = str(row.get("canal online", "") or "")
            publi_raw = row.get("Publicacion por la que se contacto el cliente", "")
            publi = str(publi_raw)[:32] if pd.notna(publi_raw) else ""
            origen = str(row.get("Origen de la pauta", "") or "")

            flags = []
            if cantidad_num >= 2:
                flags.append("MULTI-CIERRE")
            prop_str = str(prop).strip().lower()
            if not prop_str or prop_str in {"nan", "none", ""}:
                flags.append("SIN-PROPIETARIO")
            if "redes" in canal_off.lower():
                flags.append("CONTIENE-REDES")
            if canal_off.lower().strip() in {"orgánico", "organico", "orgánico "}:
                flags.append("ORGÁNICO")

            rows.append({
                "#": len(rows) + 1,
                "id_lead": id_lead,
                "propietario": prop,
                "Canal offline": canal_off,
                "canal online": canal_on,
                "Publicacion (30ch)": publi,
                "Origen pauta": origen,
                "fecha": fechas[idx].date() if pd.notna(fechas[idx]) else None,
                "col_cierre": COL_LABEL[col],
                "Cantidad": cantidad_num,
                "is_mkt": row["_mkt"],
                "flags": " | ".join(flags) if flags else "",
                "_idx": idx,
            })

    df_det = pd.DataFrame(rows)

    sep = "=" * 130
    print(sep)
    print(f"DETALLE CIERRE POR CIERRE — mayo {YEAR}  ({len(df_det)} eventos encontrados)")
    print(sep)
    if df_det.empty:
        print("(ningún cierre encontrado en mayo)")
    else:
        cols_show = ["#", "id_lead", "propietario", "Canal offline", "canal online",
                     "Publicacion (30ch)", "Origen pauta", "fecha", "col_cierre", "is_mkt", "flags"]
        print(df_det[cols_show].sort_values("fecha").to_string(index=False))

    # -------------------------------------------------------------------------
    # Leads con MÁS DE UNA columna de cierre en mayo (posible doble-conteo)
    # -------------------------------------------------------------------------
    print(f"\n{sep}")
    print("LEADS QUE APARECEN EN MÁS DE UNA COLUMNA DE CIERRE EN MAYO")
    print(sep)
    if not df_det.empty:
        cuenta_por_lead = df_det.groupby("_idx")["col_cierre"].agg(list).reset_index()
        cuenta_por_lead.columns = ["_idx", "cols_mayo"]
        multi = cuenta_por_lead[cuenta_por_lead["cols_mayo"].apply(len) > 1]
        if multi.empty:
            print("Ningún lead tiene dos o más cierres en mayo — no hay doble-conteo por esta vía.")
        else:
            print(f"¡ATENCIÓN! {len(multi)} leads tienen múltiples cierres en mayo:")
            for _, r in multi.iterrows():
                row_lead = df.loc[r["_idx"]]
                id_lead = row_lead.get("id", row_lead.get("Id", r["_idx"]))
                prop = row_lead.get("propietario", "")
                canal = row_lead.get("Canal offline", "")
                cantidad = row_lead.get("Cantidad de cierres", "")
                print(f"  idx={r['_idx']}  id={id_lead}  prop={prop}  canal={canal}"
                      f"  Cantidad={cantidad}  columnas={r['cols_mayo']}")

    # -------------------------------------------------------------------------
    # Casos especiales
    # -------------------------------------------------------------------------
    print(f"\n{sep}")
    print("CASOS ESPECIALES")
    print(sep)

    if not df_det.empty:
        # Sin propietario
        sin_prop = df_det[df_det["flags"].str.contains("SIN-PROPIETARIO", na=False)]
        print(f"\nCierres SIN propietario: {len(sin_prop)}")
        if not sin_prop.empty:
            print(sin_prop[["id_lead", "Canal offline", "fecha", "col_cierre", "is_mkt"]].to_string(index=False))

        # Orgánico
        organico = df_det[df_det["flags"].str.contains("ORGÁNICO", na=False)]
        print(f"\nCierres con Canal offline = 'Orgánico': {len(organico)}")
        if not organico.empty:
            print(organico[["id_lead", "propietario", "Canal offline", "fecha", "col_cierre", "is_mkt"]].to_string(index=False))
        else:
            # Buscar variantes no capturadas por los flags
            organico_all = df_det[df_det["Canal offline"].str.lower().str.strip().str.contains("organ", na=False)]
            if not organico_all.empty:
                print(f"  (encontradas variantes de 'orgánico' no capturadas por flag — revisá):")
                print(organico_all[["id_lead", "propietario", "Canal offline", "fecha", "is_mkt"]].to_string(index=False))

        # Multi-cierre
        multi_cierre = df_det[df_det["flags"].str.contains("MULTI-CIERRE", na=False)]
        print(f"\nCierres con Cantidad de cierres >= 2: {len(multi_cierre)}")
        if not multi_cierre.empty:
            print(multi_cierre[["id_lead", "propietario", "Canal offline", "Cantidad", "col_cierre", "is_mkt"]].to_string(index=False))

        # Contiene redes
        redes = df_det[df_det["flags"].str.contains("CONTIENE-REDES", na=False)]
        print(f"\nCierres con 'Redes' en Canal offline: {len(redes)}")
        if not redes.empty:
            print(redes[["id_lead", "propietario", "Canal offline", "fecha", "is_mkt"]].to_string(index=False))

    # -------------------------------------------------------------------------
    # Agrupado por Canal offline + Equipo
    # -------------------------------------------------------------------------
    print(f"\n{sep}")
    print("AGRUPADO POR Canal offline + Equipo (según regla vigente)")
    print(sep)
    if not df_det.empty:
        ag = (
            df_det.groupby(["Canal offline", "is_mkt"], dropna=False)
            .size()
            .reset_index(name="cierres")
            .sort_values(["is_mkt", "cierres"], ascending=[False, False])
        )
        ag["Equipo"] = ag["is_mkt"].map({True: "PAUTA", False: "REFERIDO"})
        print(ag[["Canal offline", "Equipo", "cierres"]].to_string(index=False))

    # -------------------------------------------------------------------------
    # Cierres con fechas fuera del rango estricto 2026-05-01 a 2026-05-31
    # -------------------------------------------------------------------------
    print(f"\n{sep}")
    print("VERIFICACIÓN DE FECHAS (¿hay alguna fuera del rango 01/05 - 31/05?)")
    print(sep)
    if not df_det.empty:
        fuera_rango = df_det[
            (df_det["fecha"] < date(2026, 5, 1)) |
            (df_det["fecha"] > date(2026, 5, 31))
        ]
        if fuera_rango.empty:
            print("Todas las fechas estan dentro del rango 2026-05-01 a 2026-05-31. OK")
        else:
            print(f"¡ATENCIÓN! {len(fuera_rango)} cierres con fecha fuera del rango:")
            print(fuera_rango[["id_lead", "propietario", "fecha", "col_cierre"]].to_string(index=False))

    # -------------------------------------------------------------------------
    # Resumen final vs métricas del sistema
    # -------------------------------------------------------------------------
    metrics = compute_all_metrics(df_mayo, df)

    print(f"\n{sep}")
    print("RESUMEN: DIAGNÓSTICO vs SISTEMA vs ESPERADO (Clientify verificado)")
    print(sep)
    print(f"  Cierres detectados en diagnóstico (1 fila por evento): {len(df_det)}")
    print(f"    → PAUTA en diagnóstico: {df_det['is_mkt'].sum() if not df_det.empty else 0}")
    print(f"    → REFERIDO en diagnóstico: {(~df_det['is_mkt']).sum() if not df_det.empty else 0}")
    print()

    checks = [
        ("Total cierres",            metrics.total_cierres,    EXPECTED_TOTAL),
        ("Cierres PAUTA (Marketing)", metrics.cierres_marketing, EXPECTED_MKT),
        ("Cierres REFERIDOS",        metrics.cierres_referidos, EXPECTED_REF),
    ]
    all_ok = True
    for label, real, esp in checks:
        estado = "OK   " if real == esp else "FALLA"
        if real != esp:
            all_ok = False
        diff = real - esp
        diff_str = f"(+{diff})" if diff > 0 else (f"({diff})" if diff < 0 else "")
        print(f"  [{estado}] {label}: sistema={real}  esperado={esp}  {diff_str}")

    print()
    if all_ok:
        print("✅ Todos los totales cuadran con Clientify.")
    else:
        print("❌ DIFERENCIAS DETECTADAS — revisá los detalles arriba.")

    # Desglose detallado del sistema
    print(f"\n  Desglose sistema:")
    print(f"    cierres_1 (Fecha de cierre):          {metrics.cierres_1}")
    print(f"    cierres_2 (Fecha de 2do cierre):       {metrics.cierres_2}")
    print(f"    cierres_3 (Fecha de 3er cierre):       {metrics.cierres_3}")
    print(f"    cierres_4 (Fecha de 4to cierre):       {metrics.cierres_4}")
    print(f"    cierres_adicionales (2+3+4):           {metrics.cierres_adicionales}")
    print(f"    total_cierres:                         {metrics.total_cierres}")
    print(f"    cierres_pauta_primer (solo 1ra col):   {metrics.cierres_pauta_primer}")
    print(f"    cierres_referido_primer (solo 1ra col):{metrics.cierres_referido_primer}")
    print(f"    cierres_marketing (todas las cols):    {metrics.cierres_marketing}")
    print(f"    cierres_referidos (todas las cols):    {metrics.cierres_referidos}")


if __name__ == "__main__":
    main()
