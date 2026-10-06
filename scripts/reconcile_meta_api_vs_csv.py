"""
Conciliación: gasto real diario de la API de Meta Ads (Insights) vs los CSV
de Facturación/Inversión que ya se venían subiendo a mano (ej.
`datafacturacion16012026.csv`, el export de "Interna 2026", etc.).

Por qué pueden no coincidir exacto (y está bien que no coincidan): la API
mide gasto REAL ya incurrido día por día; el CSV de Facturación solo
registra un cargo cuando el gasto acumulado llega a un umbral (~$900) — ver
`src/data_sources/meta_ads_api.py` y el diagnóstico original
(`scripts/diagnostic_meta_api.py`). Se esperan diferencias del mismo orden
de magnitud, no una igualdad exacta — un mes con gasto real alto pero cuyo
último tramo no facturó todavía mostrará API > CSV ese mes.

NO toca la UI ni ningún archivo de `src/ui/` — solo imprime una tabla
comparativa por mes a la terminal.

Uso:
    python scripts/reconcile_meta_api_vs_csv.py
    python scripts/reconcile_meta_api_vs_csv.py --csv ruta/a/archivo1.csv ruta/a/archivo2.xlsx
    python scripts/reconcile_meta_api_vs_csv.py --since 2025-01-01 --until 2026-10-06

Requiere META_ACCESS_TOKEN configurado (ver `src/config/settings.py`) — hace
una llamada REAL a la API de Meta Ads (no es un test, es una herramienta de
conciliación con datos reales).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.analytics.ad_spend import combine_ad_spend_sources, monthly_ad_spend
from src.config.settings import META_ACCESS_TOKEN
from src.data_sources.ad_spend_loader import AdSpendLoader
from src.data_sources.meta_ads_api import DEFAULT_SINCE, MetaAdsAPIError, fetch_meta_ad_spend

ROOT_DIR = Path(__file__).parent.parent
# Carpetas donde podría estar un CSV/Excel de Facturación ya descargado a
# mano en sesiones anteriores — `data/raw/` y la raíz del repo están
# gitignoreadas para archivos de datos reales (ver `.gitignore`), así que
# cualquier export real que el usuario haya dejado ahí no está versionado
# pero sigue presente en disco localmente.
SEARCH_DIRS = [ROOT_DIR, ROOT_DIR / "data" / "raw", ROOT_DIR / "scratch"]

# Nombres explícitos mencionados por el usuario — se buscan primero por
# nombre exacto en cualquiera de SEARCH_DIRS; lo que no aparezca así cae al
# descubrimiento genérico de abajo (cualquier CSV/Excel con columnas
# Fecha/Divisa/Importe reconocibles).
KNOWN_FILENAMES = ["datafacturacion16012026.csv"]


class ReconcileError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", nargs="*", default=None, help="Rutas explícitas de CSV/Excel a conciliar (si se omite, se autodetectan)")
    parser.add_argument("--since", default=DEFAULT_SINCE, help=f"Fecha de inicio del rango de la API (default {DEFAULT_SINCE})")
    parser.add_argument("--until", default=date.today().isoformat(), help="Fecha de fin del rango de la API (default hoy)")
    return parser.parse_args()


def _looks_like_billing_file(path: Path) -> bool:
    if path.suffix.lower() not in {".csv", ".xls", ".xlsx"}:
        return False
    try:
        df = AdSpendLoader(str(path)).load()
    except Exception:
        return False
    return {"Fecha", "Divisa", "Importe"}.issubset(df.columns)


def discover_csv_files(explicit: list[str] | None) -> list[Path]:
    if explicit:
        paths = [Path(p) for p in explicit]
        missing = [p for p in paths if not p.exists()]
        for p in missing:
            print(f"[warn] Archivo no encontrado, se ignora: {p}")
        return [p for p in paths if p.exists()]

    found: dict[str, Path] = {}

    for directory in SEARCH_DIRS:
        if not directory.is_dir():
            continue
        for name in KNOWN_FILENAMES:
            candidate = directory / name
            if candidate.exists():
                found[str(candidate.resolve())] = candidate

    for directory in SEARCH_DIRS:
        if not directory.is_dir():
            continue
        for path in directory.glob("*"):
            if path.is_file() and str(path.resolve()) not in found and _looks_like_billing_file(path):
                found[str(path.resolve())] = path

    return list(found.values())


def load_csv_monthly(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        try:
            frames.append(AdSpendLoader(str(path)).load())
            print(f"[info] CSV leído: {path}")
        except Exception as exc:
            print(f"[warn] No se pudo leer '{path}': {exc}")

    if not frames:
        return pd.DataFrame(columns=["Mes_Año", "Importe"])

    combined = combine_ad_spend_sources(frames)
    return monthly_ad_spend(combined)


def fetch_api_monthly(since: str, until: str) -> tuple[pd.DataFrame, list[str]]:
    if not META_ACCESS_TOKEN:
        raise ReconcileError(
            "META_ACCESS_TOKEN no está configurado. Definilo en "
            ".streamlit/secrets.toml o en .env y volvé a correr este script."
        )
    try:
        df, warnings = fetch_meta_ad_spend(token=META_ACCESS_TOKEN, since=since, until=until)
    except MetaAdsAPIError as exc:
        raise ReconcileError(f"Error llamando a la API de Meta Ads: {exc}")
    return monthly_ad_spend(df), warnings


def print_comparison_table(api_monthly: pd.DataFrame, csv_monthly: pd.DataFrame) -> None:
    api_by_month = dict(zip(api_monthly["Mes_Año"], api_monthly["Importe"])) if not api_monthly.empty else {}
    csv_by_month = dict(zip(csv_monthly["Mes_Año"], csv_monthly["Importe"])) if not csv_monthly.empty else {}

    # Orden cronológico: ambos DataFrames ya vienen ordenados por
    # (Año, Mes_num) — se recorre la unión preservando ese orden relativo.
    ordered_months: list[str] = []
    for month in list(api_monthly["Mes_Año"]) + list(csv_monthly["Mes_Año"]):
        if month not in ordered_months:
            ordered_months.append(month)

    print("\n" + "=" * 78)
    print("CONCILIACIÓN MENSUAL: API de Meta (gasto real) vs CSV (facturación)")
    print("=" * 78)
    header = f"{'Mes':18} | {'API ($)':>14} | {'CSV ($)':>14} | {'Diferencia ($)':>15} | {'%':>8}"
    print(header)
    print("-" * len(header))

    for month in ordered_months:
        api_val = api_by_month.get(month)
        csv_val = csv_by_month.get(month)
        api_str = f"{api_val:,.2f}" if api_val is not None else "—"
        csv_str = f"{csv_val:,.2f}" if csv_val is not None else "—"

        if api_val is not None and csv_val is not None:
            diff = api_val - csv_val
            pct = (diff / csv_val * 100) if csv_val else float("inf")
            diff_str = f"{diff:,.2f}"
            pct_str = f"{pct:,.1f}%"
        else:
            diff_str = "—"
            pct_str = "—"

        print(f"{month:18} | {api_str:>14} | {csv_str:>14} | {diff_str:>15} | {pct_str:>8}")

    total_api = sum(api_by_month.values())
    total_csv = sum(csv_by_month.values())
    print("-" * len(header))
    diff_total = total_api - total_csv
    pct_total = (diff_total / total_csv * 100) if total_csv else float("inf")
    print(f"{'TOTAL':18} | {total_api:>14,.2f} | {total_csv:>14,.2f} | {diff_total:>15,.2f} | {pct_total:>7,.1f}%")


def main() -> None:
    args = parse_args()

    print("=" * 78)
    print("PASO 1 — CSV de Facturación (autodetección o --csv explícito)")
    print("=" * 78)
    csv_paths = discover_csv_files(args.csv)
    if not csv_paths:
        print(
            "[warn] No se encontró ningún CSV/Excel de Facturación en "
            f"{', '.join(str(d) for d in SEARCH_DIRS)} (ni fue pasado por --csv). "
            "Se continúa mostrando solo los totales de la API — avisá si "
            "esperabas encontrar alguno."
        )
    csv_monthly = load_csv_monthly(csv_paths)

    print("\n" + "=" * 78)
    print("PASO 2 — API de Meta Ads (Insights, gasto real diario)")
    print("=" * 78)
    print(f"[info] Rango consultado: {args.since} a {args.until}")
    api_monthly, warnings = fetch_api_monthly(args.since, args.until)
    for warning in warnings:
        print(f"[warn] {warning}")

    if api_monthly.empty and csv_monthly.empty:
        print("\n[warn] No hay datos de ninguna de las 2 fuentes — nada para conciliar.")
        return

    print_comparison_table(api_monthly, csv_monthly)

    print(
        "\nRecordatorio: diferencias del mismo orden de magnitud son esperadas "
        "(API = gasto real día por día; CSV = facturación, que solo registra "
        "un cargo al llegar a un umbral) — no debería haber una igualdad exacta."
    )


if __name__ == "__main__":
    try:
        main()
    except ReconcileError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
