"""
Diagnóstico: "Creados del mes" (mkt_mask/organico_mask, basado en Canal
offline/Origen de la pauta) vs "Leads Clientify WhatsApp"/"Formulario
Facebook-CP" (basado en substring de "Etiquetas") para un período dado.

Objetivo: confirmar si `is_marketing`/`is_organico`/`is_tiktok` están
perdiendo leads que SÍ tienen una de las 2 líneas de "Etiquetas"
("305-508-5147" / "305-610-0002") pero "Canal offline" vacío/NULL.

Uso:
    python scripts/diagnostic_creados_vs_etiquetas.py <archivo.xls> <year> <month>

Ejemplo:
    python scripts/diagnostic_creados_vs_etiquetas.py data/raw/clientify_contactos.xls 2026 8
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.data_sources.excel_loader import ExcelContactsLoader
from src.analytics.filters import filter_by_month
from src.analytics.metrics import (
    is_marketing, is_organico, is_tiktok, is_cesar_augusto, _safe_str,
    compute_all_metrics,
)

pd.set_option("display.max_rows", 60)
pd.set_option("display.width", 160)

WHATSAPP_TAG = "305-508-5147"
FACEBOOK_CP_TAG = "305-610-0002"


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    file_path, year, month = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    df = ExcelContactsLoader(file_path).load()
    df_period = filter_by_month(df, pd.Timestamp(year=year, month=month, day=1).date())

    print(f"=== Período {year}-{month:02d}: {len(df_period)} leads (columna 'creado') ===\n")

    cesar_mask = df_period.apply(is_cesar_augusto, axis=1)

    etiquetas = df_period.get("Etiquetas", pd.Series("", index=df_period.index))
    etiquetas = etiquetas.apply(_safe_str).str.strip().str.lower()
    tag_whatsapp = etiquetas.str.contains(WHATSAPP_TAG, regex=False)
    tag_facebook_cp = etiquetas.str.contains(FACEBOOK_CP_TAG, regex=False)
    union_etiquetas_mask = (tag_whatsapp | tag_facebook_cp) & ~cesar_mask

    canal_off = df_period.get("Canal offline", pd.Series("", index=df_period.index))
    canal_off_norm = canal_off.apply(_safe_str).str.strip().str.lower()
    canal_off_blank = canal_off_norm.isin({"", "nan", "none"})

    # --- Punto 1 ---
    print("--- PUNTO 1: leads con línea de Etiquetas (Whatsapp o Facebook-CP), Canal offline vacío ---")
    n_union = int(union_etiquetas_mask.sum())
    n_union_blank_canal = int((union_etiquetas_mask & canal_off_blank).sum())
    print(f"Leads con 305-508-5147 o 305-610-0002 en Etiquetas (excl. César): {n_union}")
    print(f"  de esos, con Canal offline vacío/NULL: {n_union_blank_canal} "
          f"({n_union_blank_canal / n_union * 100:.1f}%)" if n_union else "  (sin leads en el universo)")

    mkt_mask = df_period.apply(is_marketing, axis=1)
    n_union_no_marketing = int((union_etiquetas_mask & ~mkt_mask).sum())
    print(f"  de esos, con is_marketing()==False (invisibles para 'Creados'): {n_union_no_marketing}\n")

    # --- Punto 3 ---
    print("--- PUNTO 3: desglose de Canal offline en el período ---")
    print(f"Canal offline vacío/NULL: {int(canal_off_blank.sum())} de {len(df_period)} "
          f"({canal_off_blank.mean() * 100:.1f}%)")
    print("\nTop 20 valores no vacíos de 'Canal offline':")
    print(canal_off_norm[~canal_off_blank].value_counts().head(20))

    organico_mask = df_period.apply(is_organico, axis=1)
    tiktok_mask = df_period.apply(is_tiktok, axis=1)
    print(f"\nis_organico()==True: {int(organico_mask.sum())}")
    print(f"is_tiktok()==True: {int(tiktok_mask.sum())}")
    print(f"  de Orgánico, con Canal offline vacío: {int((organico_mask & canal_off_blank).sum())}")
    print(f"  de TikTok, con Canal offline vacío: {int((tiktok_mask & canal_off_blank).sum())}")

    # --- Resumen cruzado ---
    print("\n--- RESUMEN ---")
    creados_mask_pre_fix = (mkt_mask | organico_mask) & ~cesar_mask
    print(f"creados PRE-fix (solo mkt_mask|organico_mask, excl. César): {int(creados_mask_pre_fix.sum())}")
    print(f"leads_clientify_whatsapp (excl. César): {int((tag_whatsapp & ~cesar_mask).sum())}")
    print(f"leads_formulario_facebook_cp (excl. César): {int((tag_facebook_cp & ~cesar_mask).sum())}")
    print(f"unión de ambas etiquetas (excl. César, sin doble conteo): {n_union}")

    # --- Post-fix (2026-09-08c): número real que da compute_all_metrics ---
    metrics_post_fix = compute_all_metrics(df_period, df)
    print(f"\ncreados POST-fix (compute_all_metrics real, incluye término de Etiquetas): {metrics_post_fix.creados}")
    print("(esperado: >= creados PRE-fix, y >= la unión de etiquetas de arriba, "
          "más lo que aporten TikTok/Orgánico por Canal offline poblado)")


if __name__ == "__main__":
    main()
