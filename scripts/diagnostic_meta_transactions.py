"""
Diagnóstico AISLADO del endpoint de cobros/transacciones de Meta Ads
(`GET /act_{id}/transactions`) — Parte B de la tarea "Nueva gráfica: Gasto
facturado por mes". SOLO LECTURA, NO integra nada a la app todavía: hoy
`src/ui/sections/ad_spend_billed.py` sigue dependiendo del CSV de
Facturación subido a mano (ver `scripts/diagnostic_meta_api.py` para el
diagnóstico equivalente de Insights, que SÍ se integró).

Objetivo: confirmar si el token actual (`META_ACCESS_TOKEN`, el mismo que ya
usa `src/data_sources/meta_ads_api.py` para Insights) tiene permiso para
leer facturación directamente desde la API — lo que eliminaría la
necesidad del CSV manual en el futuro. Si falla por permisos, reporta
exactamente qué permiso falta (ej. `business_management`) para que el
usuario pueda pedirlo en el Business Manager.

Para cada cuenta, en orden:
  1. `GET /act_{id}/transactions` (endpoint de facturación a nivel de
     cuenta publicitaria).
  2. Si (1) falla, intenta descubrir un `business_id` asociado al token vía
     `GET /me/businesses` y probar `GET /{business_id}/adaccounts` como
     fallback exploratorio — reporta igual si tampoco funciona, no asume
     que existe un ID de negocio configurado en ningún lado.

Seguridad: mismo patrón que `meta_ads_api.py` — token por header
`Authorization: Bearer`, nunca en query string ni impreso en ningún lado.

Uso:
    python scripts/diagnostic_meta_transactions.py

Requiere META_ACCESS_TOKEN configurado (ver `src/config/settings.py`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from src.config.settings import (
    META_ACCESS_TOKEN,
    META_AD_ACCOUNT_ID_CONTINGENCIA,
    META_AD_ACCOUNT_ID_SM_CP_INTERNA,
    META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS,
)
from src.data_sources.meta_ads_api import GRAPH_BASE_URL, _sanitize

SCRATCH_DIR = Path(__file__).parent.parent / "scratch"

ACCOUNTS = [
    ("SM CP Interna", META_AD_ACCOUNT_ID_SM_CP_INTERNA),
    ("Soluciones Migratorias", META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS),
    ("Contingencia", META_AD_ACCOUNT_ID_CONTINGENCIA),
]


class DiagnosticError(RuntimeError):
    pass


def _build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _get(session: requests.Session, url: str, params: dict | None, token: str, timeout: int = 30) -> tuple[bool, dict | str]:
    """GET simple, sin reintentos (diagnóstico de 1 sola pasada) — devuelve
    `(ok, payload_o_mensaje_de_error_sanitizado)`."""
    try:
        resp = session.get(url, params=params, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        return False, _sanitize(str(exc), token)

    try:
        payload = resp.json()
    except ValueError:
        return False, _sanitize(f"HTTP {resp.status_code}, respuesta no-JSON: {resp.text[:300]}", token)

    if not resp.ok:
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = err.get("code", resp.status_code)
        subcode = err.get("error_subcode", "")
        msg = err.get("message", str(payload))
        detail = f"HTTP {resp.status_code} (code={code}{f', subcode={subcode}' if subcode else ''}): {msg}"
        return False, _sanitize(detail, token)

    return True, payload


def try_transactions_endpoint(session: requests.Session, account_id: str, token: str) -> tuple[bool, dict | str]:
    url = f"{GRAPH_BASE_URL}/act_{account_id}/transactions"
    return _get(session, url, params={"limit": 500}, token=token)


def try_discover_business_and_fallback(session: requests.Session, token: str) -> None:
    print("  [info] Intentando fallback exploratorio: GET /me/businesses ...")
    ok, payload = _get(session, f"{GRAPH_BASE_URL}/me/businesses", params=None, token=token)
    if not ok:
        print(f"  [warn] /me/businesses también falló: {payload}")
        return

    businesses = payload.get("data", []) if isinstance(payload, dict) else []
    if not businesses:
        print("  [warn] /me/businesses respondió OK pero sin negocios asociados a este token.")
        return

    for biz in businesses:
        biz_id = biz.get("id")
        biz_name = biz.get("name", "?")
        print(f"  [info] Negocio encontrado: '{biz_name}' (id={biz_id}) — probando /{{business_id}}/adaccounts ...")
        ok2, payload2 = _get(session, f"{GRAPH_BASE_URL}/{biz_id}/adaccounts", params={"limit": 5}, token=token)
        if ok2:
            count = len(payload2.get("data", [])) if isinstance(payload2, dict) else 0
            print(f"  [info] /{biz_id}/adaccounts respondió OK ({count} cuenta(s) visibles vía este negocio).")
        else:
            print(f"  [warn] /{biz_id}/adaccounts falló: {payload2}")


def analyze_transactions(account_label: str, account_id: str, payload: dict) -> None:
    records = payload.get("data", []) if isinstance(payload, dict) else []
    print(f"  Registros recibidos: {len(records)}")
    if not records:
        print("  [warn] 0 registros — sin movimientos de facturación en el rango que trae el endpoint por default.")
        return

    # Campos reales a confirmar empíricamente — se imprime el primer
    # registro completo para no asumir nombres de campo sin evidencia.
    print(f"  Primer registro completo: {json.dumps(records[0], ensure_ascii=False)}")

    possible_date_fields = ["time", "created_time", "billing_period_start", "charge_date"]
    possible_amount_fields = ["billed_amount", "amount", "value"]

    date_field = next((f for f in possible_date_fields if f in records[0]), None)
    amount_field = None
    for f in possible_amount_fields:
        if f in records[0]:
            amount_field = f
            break
        # billed_amount suele venir anidado como {"amount": "...", "currency": "USD"}
        if isinstance(records[0].get(f), dict) and "amount" in records[0][f]:
            amount_field = f
            break

    if date_field:
        dates = sorted(str(r.get(date_field, "")) for r in records if r.get(date_field))
        print(f"  Rango de fechas (campo '{date_field}'): {dates[0]} a {dates[-1]}")
    else:
        print(f"  [warn] No se encontró un campo de fecha reconocible entre {possible_date_fields}.")

    if amount_field:
        total = 0.0
        for r in records:
            val = r.get(amount_field)
            if isinstance(val, dict):
                val = val.get("amount")
            try:
                total += float(val)
            except (TypeError, ValueError):
                pass
        print(f"  Total (campo '{amount_field}'): {total:,.2f}")
    else:
        print(f"  [warn] No se encontró un campo de monto reconocible entre {possible_amount_fields}.")


def main() -> None:
    if not META_ACCESS_TOKEN:
        raise DiagnosticError(
            "META_ACCESS_TOKEN no está configurado. Definilo en "
            ".streamlit/secrets.toml o en .env y volvé a correr este script."
        )

    SCRATCH_DIR.mkdir(exist_ok=True)
    session = _build_session(META_ACCESS_TOKEN)

    any_success = False
    for account_label, account_id in ACCOUNTS:
        print("=" * 78)
        print(f"Cuenta: {account_label} (act_{account_id})")
        print("=" * 78)

        ok, payload = try_transactions_endpoint(session, account_id, META_ACCESS_TOKEN)
        if not ok:
            print(f"  [ERROR] /act_{account_id}/transactions falló: {payload}")
            try_discover_business_and_fallback(session, META_ACCESS_TOKEN)
            continue

        any_success = True
        out_path = SCRATCH_DIR / f"meta_transactions_sample_{account_id}.json"
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [info] JSON crudo guardado en {out_path}")
        analyze_transactions(account_label, account_id, payload)

    print("\n" + "=" * 78)
    print("RESUMEN")
    print("=" * 78)
    if any_success:
        print("Al menos una cuenta respondió OK — ver detalle arriba y comparar contra el CSV manualmente.")
    else:
        print(
            "Ninguna cuenta pudo leer /transactions con este token. Revisá el mensaje de error de "
            "cada cuenta arriba — si menciona un permiso (ej. 'business_management', "
            "'ads_management', 'Missing Permissions'), hay que agregarlo al token/app en el "
            "Business Manager de Meta para poder usar este endpoint en el futuro."
        )
    print("\nEsto NO modificó nada en src/analytics/ ni src/ui/ — solo diagnóstico de lectura.")


if __name__ == "__main__":
    try:
        main()
    except DiagnosticError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
