"""
Diagnóstico AISLADO de la Meta Marketing API (Insights) — paso 1 del plan de
integración de Meta Ads como fuente de datos alternativa al CSV manual de
Meta Ads Manager que hoy se sube en "Marketing e Inversión". NO toca
`src/analytics/ad_spend*.py` ni `src/ui/`, solo lee y guarda evidencia.

Decisión clave de esta integración (confirmada con el usuario 2026-10-06):
usar el endpoint de INSIGHTS (gasto real diario), no el de /transactions
(facturación) — Meta solo registra una factura/cargo cuando el gasto
acumulado llega a un umbral (~$900 en esta cuenta), así que un gasto real ya
incurrido pero aún no facturado quedaría invisible si se usara facturación
como fuente. Insights da `spend` real día por día, sin ese problema.

Qué hace este script:
  - Para cada una de las 3 cuentas publicitarias configuradas en
    `src/config/settings.py` (SM CP Interna, Soluciones Migratorias,
    Contingencia), llama a `GET /act_<id>/insights` con
    `fields=spend,date_start,date_stop`, `time_increment=1` (desglose diario)
    y `time_range` cubriendo desde 2025-01-01 hasta hoy.
  - Imprime cuántos registros diarios trae cada cuenta, el rango de fechas
    real cubierto, y la suma total de `spend` — para comparar a ojo contra
    los CSV de facturación ya existentes (mismo orden de magnitud esperado,
    NO el mismo número exacto, porque ahora medimos gasto real, no facturado).
  - Si una cuenta da error (sin permiso, no accesible con este token, etc.)
    lo reporta y sigue con las demás — no tumba el script completo.
  - Persiste el JSON crudo de cada cuenta en
    `scratch/meta_insights_sample_<account_id>.json` (gitignored) para no
    depender de la memoria de esta conversación en sesiones futuras.

Versión de API: se confirmó por búsqueda web (2026-10-06) que v26.0 es la
versión estable más reciente del Graph API (lanzada 2026-07-29) — v21.0
(usada en el pedido original) ya expiró. Usamos v26.0 por default, con
`--api-version` para pisarla si hiciera falta.

Requiere META_ACCESS_TOKEN configurado (en .streamlit/secrets.toml local, o
en .env) — se lee vía `src.config.settings._get_secret()`, igual que
CLIENTIFY_API_TOKEN. No pega el token en ningún otro lado ni en los JSON
persistidos.

Uso:
    python scripts/diagnostic_meta_api.py
    python scripts/diagnostic_meta_api.py --since 2025-01-01 --until 2026-10-06
    python scripts/diagnostic_meta_api.py --api-version v26.0
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from src.config.settings import (
    META_ACCESS_TOKEN,
    META_AD_ACCOUNT_ID_SM_CP_INTERNA,
    META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS,
    META_AD_ACCOUNT_ID_CONTINGENCIA,
)

SCRATCH_DIR = Path(__file__).parent.parent / "scratch"

ACCOUNTS = [
    ("SM CP Interna", META_AD_ACCOUNT_ID_SM_CP_INTERNA),
    ("Soluciones Migratorias", META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS),
    ("Contingencia", META_AD_ACCOUNT_ID_CONTINGENCIA),
]

DEFAULT_API_VERSION = "v26.0"


class DiagnosticError(RuntimeError):
    """Error claro y accionable, para no mostrar un traceback genérico."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", default="2025-01-01", help="Fecha de inicio del rango (default 2025-01-01)")
    parser.add_argument("--until", default=date.today().isoformat(), help="Fecha de fin del rango (default hoy)")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION, help=f"Versión del Graph API (default {DEFAULT_API_VERSION})")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout por request en segundos (default 30)")
    return parser.parse_args()


def safe_get_insights(
    session: requests.Session, base_url: str, account_id: str, account_label: str,
    since: str, until: str, timeout: int,
) -> dict:
    """GET /act_<id>/insights con manejo de errores claro — nunca deja pasar
    un traceback genérico, siempre devuelve algo reportable."""
    url = f"{base_url}/act_{account_id}/insights"
    params = {
        "fields": "spend,date_start,date_stop",
        "time_increment": 1,
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": 500,
    }

    all_data: list[dict] = []
    page_num = 1
    next_url = url
    next_params: dict | None = params

    while next_url:
        try:
            resp = session.get(next_url, params=next_params, timeout=timeout)
        except requests.exceptions.ConnectTimeout:
            raise DiagnosticError(f"[{account_label}] Timeout conectando a {next_url}.")
        except requests.exceptions.ConnectionError as exc:
            raise DiagnosticError(f"[{account_label}] No se pudo conectar: {exc}")
        except requests.exceptions.RequestException as exc:
            raise DiagnosticError(f"[{account_label}] Error de red: {exc}")

        try:
            payload = resp.json()
        except ValueError:
            raise DiagnosticError(f"[{account_label}] Respuesta no es JSON válido:\n{resp.text[:500]}")

        if not resp.ok:
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            msg = err.get("message", resp.text[:300])
            code = err.get("code", resp.status_code)
            raise DiagnosticError(
                f"[{account_label}] HTTP {resp.status_code} (error code {code}) en act_{account_id}: {msg}"
            )

        page_data = payload.get("data", [])
        all_data.extend(page_data)
        print(f"  [info] Página {page_num}: {len(page_data)} registros diarios (acumulado {len(all_data)}).")

        next_url = payload.get("paging", {}).get("next")
        next_params = None  # 'next' ya trae los params codificados
        page_num += 1

    return {"data": all_data}


def analyze_and_report(account_label: str, account_id: str, result: dict) -> None:
    records = result.get("data", [])
    print(f"\n  Registros diarios recibidos: {len(records)}")

    if not records:
        print("  [warn] 0 registros — la cuenta no tiene gasto registrado en el rango, "
              "o el token no tiene permiso de lectura de insights sobre ella.")
        return

    dates = sorted(r["date_start"] for r in records if r.get("date_start"))
    total_spend = sum(float(r.get("spend", 0) or 0) for r in records)

    print(f"  Rango de fechas real cubierto: {dates[0]} a {dates[-1]}")
    print(f"  Suma total de spend (gasto real, USD): ${total_spend:,.2f}")


def main() -> None:
    args = parse_args()

    if not META_ACCESS_TOKEN:
        raise DiagnosticError(
            "META_ACCESS_TOKEN no está configurado. Definilo en "
            ".streamlit/secrets.toml (local, copiando secrets.toml.example) "
            "o en .env, y volvé a correr este script."
        )

    SCRATCH_DIR.mkdir(exist_ok=True)

    base_url = f"https://graph.facebook.com/{args.api_version}"
    print(f"[info] Graph API version: {args.api_version}")
    print(f"[info] Rango consultado: {args.since} a {args.until}\n")

    session = requests.Session()
    session.params = {"access_token": META_ACCESS_TOKEN}

    results_summary = []

    for account_label, account_id in ACCOUNTS:
        print("=" * 78)
        print(f"Cuenta: {account_label} (act_{account_id})")
        print("=" * 78)
        try:
            result = safe_get_insights(session, base_url, account_id, account_label, args.since, args.until, args.timeout)
        except DiagnosticError as exc:
            print(f"  [ERROR] {exc}")
            results_summary.append((account_label, account_id, "ERROR", str(exc)))
            continue

        out_path = SCRATCH_DIR / f"meta_insights_sample_{account_id}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [info] JSON crudo guardado en {out_path}")

        analyze_and_report(account_label, account_id, result)
        records = result.get("data", [])
        total_spend = sum(float(r.get("spend", 0) or 0) for r in records)
        results_summary.append((account_label, account_id, "OK", f"{len(records)} días, ${total_spend:,.2f}"))

    print("\n" + "=" * 78)
    print("RESUMEN")
    print("=" * 78)
    for label, acc_id, status, detail in results_summary:
        print(f"  {label:30} (act_{acc_id}): {status} — {detail}")

    print("\nEsto NO modificó nada en src/analytics/ ni src/ui/, ni implementó el cliente.")
    print(f"Archivos persistidos en {SCRATCH_DIR} (gitignored) para futuras sesiones.")


if __name__ == "__main__":
    try:
        main()
    except DiagnosticError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
