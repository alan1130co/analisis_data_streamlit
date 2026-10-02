"""
Diagnóstico (SOLO LECTURA, sin fixes): busca contactos cuya fecha "creado"
cae DESPUÉS del mes de cierre seleccionado — caso lógicamente imposible (un
lead no puede haberse creado después de haber cerrado).

Motivado por: en "Cierres de Clientify-Whatsapp y Formulario Facebook-CP por
mes de origen" (pauta_vs_referidos_antiguedad.py -> breakdowns.py ->
cierres_whatsapp_facebook_cp_por_mes_origen), con Período de cierre = Agosto
2026, la torta de Clientify-Whatsapp muestra una porción "Sep 2026: 1" como
mes de ORIGEN (creación).

Para cada cierre válido (estado != "inactivo") del mes/año pedido, con
"Canal offline" en {Clientify - Whatsapp, Formulario de Facebook - Cliente
Potencial} (mismo filtro que la función real), compara "creado" contra la
fecha de cierre. Imprime CUALQUIER caso donde creado > fecha de cierre,
sin importar si cae en el mismo mes o en uno posterior — para no perderse
casos límite de día (p.ej. creado 31/08 y cierre 05/08 no es "otro mes" pero
sigue siendo imposible).

No implementa ningún fix — es puramente informativo.

Uso:
    python scripts/diagnostic_creado_posterior_a_cierre.py <archivo.xls> <year> <month>

Ejemplo:
    python scripts/diagnostic_creado_posterior_a_cierre.py data/raw/clientify_contactos.xls 2026 8
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.metrics import CLOSE_DATE_COLS, valid_closure_estado_mask, _safe_str

pd.set_option("display.max_rows", 200)
pd.set_option("display.max_colwidth", 60)
pd.set_option("display.width", 240)

COL_LABELS = {
    "Fecha de cierre": "1ra (Fecha de cierre)",
    "Fecha de segundo cierre": "2da (Fecha de segundo cierre)",
    "Fecha de tercer cierre": "3ra (Fecha de tercer cierre)",
    "Fecha de 4to cierre": "4ta (Fecha de 4to cierre)",
}

NAME_CANDIDATES = ["nombre", "Nombre", "Contacto", "contacto", "Nombre completo", "email", "Email"]

_CANALES_WHATSAPP_FACEBOOK_CP = {
    "clientify - whatsapp": "Clientify - Whatsapp",
    "formulario de facebook - cliente potencial": "Formulario de Facebook - Cliente Potencial",
}


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

    if "creado" not in df.columns or "Canal offline" not in df.columns:
        print("Faltan columnas 'creado' o 'Canal offline' en el Excel cargado.")
        return

    name_col_used = next((c for c in NAME_CANDIDATES if c in df.columns), None)
    print(f"Columna usada para identificar contacto: {name_col_used!r}")
    print(f"Archivo: {file_path}")
    print(f"Período de cierre analizado: {year}-{month:02d}\n")

    active = valid_closure_estado_mask(df)
    canal_off_norm = df["Canal offline"].apply(_safe_str).str.strip().str.lower()
    canal_mask = canal_off_norm.isin(_CANALES_WHATSAPP_FACEBOOK_CP.keys())
    creado = pd.to_datetime(df["creado"], errors="coerce")

    anomalias = []
    for col in CLOSE_DATE_COLS:
        if col not in df.columns:
            continue
        dt = pd.to_datetime(df[col], errors="coerce")
        in_month = (dt.dt.year == year) & (dt.dt.month == month) & active & canal_mask
        if not in_month.any():
            continue
        for idx in df.index[in_month]:
            c = creado.loc[idx]
            f = dt.loc[idx]
            if pd.isna(c):
                continue
            if c > f:
                anomalias.append({
                    "index": idx,
                    "contacto": _contact_label(df, idx),
                    "propietario": _safe_str(df.at[idx, "propietario"]) if "propietario" in df.columns else "",
                    "canal_offline": canal_off_norm.loc[idx],
                    "columna_cierre": COL_LABELS.get(col, col),
                    "creado": c,
                    "fecha_cierre": f,
                    "creado_raw_dtype": type(df.at[idx, "creado"]).__name__,
                    "estado": _safe_str(df.at[idx, "estado"]) if "estado" in df.columns else "",
                })

    if not anomalias:
        print("No se encontraron casos donde 'creado' sea posterior a la fecha de cierre, "
              "para este período/canal. El caso reportado puede no estar en este archivo "
              "(archivo desactualizado) o el período/canal no coincide exactamente.")
        return

    anomalias_df = pd.DataFrame(anomalias)
    print(f"{'=' * 100}")
    print(f"ANOMALÍAS ENCONTRADAS: {len(anomalias_df)} caso(s) donde 'creado' > fecha de cierre")
    print("=" * 100)
    display_cols = [
        "index", "contacto", "propietario", "canal_offline", "columna_cierre",
        "creado", "fecha_cierre", "creado_raw_dtype", "estado",
    ]
    print(anomalias_df[display_cols].to_string(index=False))

    # Chequeo adicional: ¿el valor crudo de 'creado' en el Excel, ANTES del
    # parseo de ExcelContactsLoader, es distinto a lo que vemos ya parseado?
    # Esto ayuda a distinguir bug de parseo (causa #2) vs. dato mal cargado
    # en Clientify (causa #3).
    print(f"\n{'=' * 100}")
    print("Valor crudo de 'creado' leído directamente del Excel (sin dayfirst=True ni coerce)")
    print("=" * 100)
    raw = pd.read_excel(file_path, sheet_name="Contactos")
    raw.columns = [c.strip() for c in raw.columns]
    for row in anomalias:
        idx = row["index"]
        raw_val = raw.at[idx, "creado"] if "creado" in raw.columns and idx in raw.index else "N/A"
        print(f"index={idx}  contacto={row['contacto']!r}  creado_crudo_excel={raw_val!r}  "
              f"creado_parseado={row['creado']}")


if __name__ == "__main__":
    main()
