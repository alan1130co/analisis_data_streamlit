"""
Diagnóstico v2 de FACTURACIÓN de Meta por API (solo lectura, NO integra
nada a la app todavía) — corrige la conclusión débil del diagnóstico
anterior (`scripts/diagnostic_meta_transactions.py`): esa versión concluyó
"falta business_management" a partir de que `/{business_id}/adaccounts`
fallaba, pero ESE EDGE NO EXISTE en la API real (los válidos son
`owned_ad_accounts`/`client_ad_accounts`) — así que esa prueba no probaba
nada sobre permisos, solo probaba un endpoint inventado. Esta versión usa
los edges reales y confirma permisos empíricamente antes de concluir nada.

Pasos (en este orden, cada uno imprime su resultado antes de seguir):
  1. `GET /me/permissions` — permisos concedidos/declinados del token real.
  2. `GET /{business_id}/owned_ad_accounts` + `/client_ad_accounts` para
     cada uno de los 11 negocios de `/me/businesses`, para identificar cuál
     negocio es dueño/administra cada una de las 3 cuentas objetivo.
  3. `GET /{business_id}/business_invoices` (parámetros confirmados contra
     la documentación oficial 2026-10: `start_date`/`end_date` filtran por
     PERÍODO DE FACTURACIÓN, `issue_start_date`/`issue_end_date` por fecha
     de EMISIÓN — ver docstring de `fetch_business_invoices` más abajo)
     sobre el/los negocio(s) identificados en el paso 2, con fallback a
     tramos trimestrales si el rango completo falla.
  4. Alternativas por cuenta: `/act_{id}/transactions` en v26.0 Y v19.0,
     `/act_{id}?fields=amount_spent,balance,currency,account_status,
     funding_source_details`, y `/act_{id}/activities` (paginado completo,
     filtrando `event_type == "ad_account_billing_charge"` — es el único
     de los 4 que trae cobros reales con monto, ver `extract_billing_charges`).
  5. Agrega esos cobros por mes (convirtiendo `event_time` de UTC a
     `APP_TIMEZONE` — el CSV pone la fecha en zona LOCAL, no UTC) y compara
     contra los 2 CSV de facturación ya existentes (rutas hardcodeadas más
     abajo, ver `CSV_PATHS`).
  6. Todo el JSON crudo que SÍ respondió se guarda en `scratch/` (gitignored).
     El token nunca se imprime ni se loguea — todo mensaje de error pasa por
     `meta_ads_api._sanitize()` antes de mostrarse.

Uso:
    python scripts/diagnostic_meta_billing.py

Requiere META_ACCESS_TOKEN configurado (ver `src/config/settings.py`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import requests

from src.analytics.ad_spend import combine_ad_spend_sources, monthly_ad_spend_with_period
from src.config.settings import (
    APP_TIMEZONE,
    META_ACCESS_TOKEN,
    META_AD_ACCOUNT_ID_CONTINGENCIA,
    META_AD_ACCOUNT_ID_SM_CP_INTERNA,
    META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS,
)
from src.data_sources.ad_spend_loader import AdSpendLoader
from src.data_sources.meta_ads_api import GRAPH_BASE_URL, _build_session, _sanitize

SCRATCH_DIR = Path(__file__).parent.parent / "scratch"

TARGET_ACCOUNTS = [
    ("SM CP Interna", META_AD_ACCOUNT_ID_SM_CP_INTERNA),
    ("Soluciones Migratorias", META_AD_ACCOUNT_ID_SOLUCIONES_MIGRATORIAS),
    ("Contingencia", META_AD_ACCOUNT_ID_CONTINGENCIA),
]

OLD_API_VERSION_FALLBACK = "v19.0"

# CSV de facturación reales ya descargados a mano — rutas absolutas dadas
# por el usuario (fuera del repo, no gitignoreadas porque no están en el
# repo para empezar).
CSV_PATHS = [
    r"C:\Users\alanc\OneDrive\Escritorio\dato facturacion met a\datafacturacion16012026.csv",
    r"C:\Users\alanc\OneDrive\Escritorio\dato facturacion met a\2026-01-16--2026-10-06_Resumen_Facturación.csv",
]


class DiagnosticError(RuntimeError):
    pass


def _get(session: requests.Session, url: str, params: dict | None, token: str, timeout: int = 30) -> dict:
    """GET sin reintentos (diagnóstico de 1 sola pasada). Devuelve SIEMPRE
    un dict con forma uniforme: `{"ok": bool, "payload": ..., "error": {...}
    o None}` — nunca lanza, para que el script siga con el resto de
    pruebas sin importar qué tan mal responda una llamada puntual. El
    `error` (si existe) viene con el mensaje YA sanitizado (sin token)."""
    try:
        resp = session.get(url, params=params, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "payload": None, "error": {"message": _sanitize(str(exc), token)}}

    try:
        payload = resp.json()
    except ValueError:
        return {
            "ok": False, "payload": None,
            "error": {"message": _sanitize(f"HTTP {resp.status_code}, respuesta no-JSON: {resp.text[:300]}", token)},
        }

    if not resp.ok:
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        sanitized_err = {
            "message": _sanitize(err.get("message", str(payload)), token),
            "type": err.get("type"),
            "code": err.get("code"),
            "error_subcode": err.get("error_subcode"),
            "error_user_title": _sanitize(err.get("error_user_title", ""), token) or None,
            "error_user_msg": _sanitize(err.get("error_user_msg", ""), token) or None,
            "http_status": resp.status_code,
        }
        return {"ok": False, "payload": None, "error": sanitized_err}

    return {"ok": True, "payload": payload, "error": None}


def _fmt_error(error: dict) -> str:
    bits = [f"HTTP {error.get('http_status', '?')}", f"code={error.get('code', '?')}"]
    if error.get("error_subcode"):
        bits.append(f"subcode={error['error_subcode']}")
    if error.get("type"):
        bits.append(f"type={error['type']}")
    detail = ", ".join(bits)
    msg = error.get("message", "")
    extra = error.get("error_user_msg") or ""
    return f"{detail}: {msg}" + (f" | user_msg: {extra}" if extra else "")


def paginate_all(session: requests.Session, url: str, params: dict | None, token: str) -> tuple[list[dict], dict | None]:
    """Sigue `paging.next` hasta agotar páginas. Devuelve `(registros, error)`
    — `error` no-None si CUALQUIER página falló (se detiene ahí, devuelve lo
    que ya se acumuló hasta ese punto)."""
    records: list[dict] = []
    next_url, next_params = url, params
    while next_url:
        result = _get(session, next_url, next_params, token)
        if not result["ok"]:
            return records, result["error"]
        payload = result["payload"]
        records.extend(payload.get("data", []))
        next_url = (payload.get("paging") or {}).get("next")
        next_params = None
    return records, None


# --- PASO 1: /me/permissions -------------------------------------------

def step1_permissions(session: requests.Session, token: str) -> None:
    print("=" * 78)
    print("PASO 1 — GET /me/permissions")
    print("=" * 78)
    result = _get(session, f"{GRAPH_BASE_URL}/me/permissions", None, token)
    if not result["ok"]:
        print(f"[ERROR] /me/permissions falló: {_fmt_error(result['error'])}")
        return

    perms = {p["permission"]: p["status"] for p in result["payload"].get("data", [])}
    (SCRATCH_DIR / "meta_me_permissions.json").write_text(
        json.dumps(result["payload"], indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"{'Permiso':35} | Estado")
    print("-" * 50)
    for perm, status in sorted(perms.items()):
        print(f"{perm:35} | {status}")

    print()
    for key in ("business_management", "ads_read", "ads_management"):
        status = perms.get(key, "NO PRESENTE EN LA LISTA")
        print(f"  -> {key}: {status}")


# --- PASO 2: dueño de cada cuenta objetivo ------------------------------

def _fetch_business_ad_accounts(session: requests.Session, business_id: str, edge: str, token: str) -> tuple[list[dict], dict | None]:
    url = f"{GRAPH_BASE_URL}/{business_id}/{edge}"
    return paginate_all(session, url, {"fields": "id,name,account_id", "limit": 200}, token)


def step2_find_account_owners(session: requests.Session, token: str) -> dict[str, dict]:
    print("\n" + "=" * 78)
    print("PASO 2 — ¿qué negocio es dueño/administra cada cuenta objetivo?")
    print("=" * 78)

    biz_result = _get(session, f"{GRAPH_BASE_URL}/me/businesses", {"limit": 50}, token)
    if not biz_result["ok"]:
        print(f"[ERROR] /me/businesses falló: {_fmt_error(biz_result['error'])}")
        return {}

    businesses = biz_result["payload"].get("data", [])
    print(f"[info] {len(businesses)} negocio(s) encontrados vía /me/businesses.")

    target_ids = {acc_id for _, acc_id in TARGET_ACCOUNTS}
    owner_by_account: dict[str, dict] = {}
    all_accounts_seen: dict[str, list[dict]] = {}

    for biz in businesses:
        biz_id, biz_name = biz.get("id"), biz.get("name", "?")
        for edge, relation in (("owned_ad_accounts", "owned"), ("client_ad_accounts", "client")):
            records, error = _fetch_business_ad_accounts(session, biz_id, edge, token)
            if error:
                print(f"  [warn] {biz_name} ({biz_id}) / {edge}: {_fmt_error(error)}")
                continue
            all_accounts_seen.setdefault(biz_id, []).extend(records)
            for acc in records:
                acc_id = acc.get("account_id")
                if acc_id in target_ids:
                    owner_by_account[acc_id] = {
                        "business_id": biz_id, "business_name": biz_name,
                        "relation": relation, "ad_account_name": acc.get("name"),
                    }

    (SCRATCH_DIR / "meta_business_ad_accounts_scan.json").write_text(
        json.dumps(all_accounts_seen, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print()
    for label, acc_id in TARGET_ACCOUNTS:
        owner = owner_by_account.get(acc_id)
        if owner:
            print(
                f"  {label} (act_{acc_id}) -> negocio '{owner['business_name']}' "
                f"(id={owner['business_id']}, relación={owner['relation']}, "
                f"nombre de cuenta en ese negocio='{owner['ad_account_name']}')"
            )
        else:
            print(f"  {label} (act_{acc_id}) -> NO encontrada en ningún owned_ad_accounts/client_ad_accounts visible.")

    return owner_by_account


# --- PASO 3: /{business_id}/business_invoices ---------------------------

def fetch_business_invoices(session: requests.Session, business_id: str, since: str, until: str, token: str) -> tuple[list[dict], dict | None]:
    """`start_date`/`end_date` filtran por PERÍODO DE FACTURACIÓN (billing
    period), EXCLUSIVO en ambos extremos — confirmado contra la
    documentación oficial de `Business/business_invoices` (2026-10):
    default de `end_date` es hoy, default de `start_date` es "hace 6
    meses". NO se pide `fields=` explícito a propósito: el objeto real
    (`OmegaCustomerTrx`) no tiene sus campos documentados públicamente con
    nombres exactos — se trae el set default del servidor y se imprime el
    primer registro completo para descubrir empíricamente qué trae.
    """
    url = f"{GRAPH_BASE_URL}/{business_id}/business_invoices"
    return paginate_all(session, url, {"start_date": since, "end_date": until, "limit": 200}, token)


def _quarterly_ranges(since: str, until: str) -> list[tuple[str, str]]:
    start = pd.Timestamp(since)
    end = pd.Timestamp(until)
    ranges = []
    cursor = start
    while cursor <= end:
        quarter_end = min(cursor + pd.DateOffset(months=3) - pd.DateOffset(days=1), end)
        ranges.append((cursor.strftime("%Y-%m-%d"), quarter_end.strftime("%Y-%m-%d")))
        cursor = quarter_end + pd.DateOffset(days=1)
    return ranges


def step3_business_invoices(session: requests.Session, business_ids: list[tuple[str, str]], token: str) -> list[dict]:
    print("\n" + "=" * 78)
    print("PASO 3 — GET /{business_id}/business_invoices (2025-01-01 a hoy)")
    print("=" * 78)

    since, until = "2025-01-01", pd.Timestamp.now().strftime("%Y-%m-%d")
    all_invoices: list[dict] = []

    for business_name, business_id in business_ids:
        print(f"\n  Negocio: {business_name} ({business_id})")
        records, error = fetch_business_invoices(session, business_id, since, until, token)

        if error:
            print(f"    [warn] Rango completo falló ({_fmt_error(error)}) — reintentando por trimestre...")
            records = []
            for q_since, q_until in _quarterly_ranges(since, until):
                q_records, q_error = fetch_business_invoices(session, business_id, q_since, q_until, token)
                if q_error:
                    print(f"    [ERROR] Tramo {q_since} a {q_until}: {_fmt_error(q_error)}")
                    continue
                print(f"    [info] Tramo {q_since} a {q_until}: {len(q_records)} factura(s).")
                records.extend(q_records)

        print(f"    Total acumulado para este negocio: {len(records)} factura(s)/registro(s).")
        if records:
            print(f"    Primer registro completo: {json.dumps(records[0], ensure_ascii=False)}")
        all_invoices.extend(records)

    if all_invoices:
        (SCRATCH_DIR / "meta_business_invoices.json").write_text(
            json.dumps(all_invoices, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n  [info] JSON crudo guardado en {SCRATCH_DIR / 'meta_business_invoices.json'}")

    return all_invoices


# --- PASO 4: alternativas por cuenta ------------------------------------

def fetch_all_activities(session: requests.Session, account_id: str, since: str, until: str, token: str) -> tuple[list[dict], dict | None]:
    """Pagina TODO `/act_{id}/activities` en el rango — es el único de los 4
    endpoints probados que realmente expone cobros (ver más abajo:
    `event_type == "ad_account_billing_charge"`, con `extra_data.new_value`
    en centavos, `extra_data.currency` y `extra_data.transaction_id` —
    este último coincide BYTE A BYTE con la columna "Identificador de la
    transacción" del CSV de Facturación, confirmado empíricamente)."""
    url = f"{GRAPH_BASE_URL}/act_{account_id}/activities"
    params = {"limit": 100, "fields": "event_type,event_time,extra_data", "since": since, "until": until}
    return paginate_all(session, url, params, token)


def extract_billing_charges(records: list[dict]) -> list[dict]:
    charges = []
    for r in records:
        if r.get("event_type") != "ad_account_billing_charge":
            continue
        try:
            extra = json.loads(r.get("extra_data", "{}"))
        except json.JSONDecodeError:
            continue
        charges.append({
            "event_time": r["event_time"],
            "amount": extra.get("new_value", 0) / 100.0,
            "currency": extra.get("currency"),
            "transaction_id": extra.get("transaction_id"),
        })
    return charges


def step4_account_alternatives(
    session_v26: requests.Session, session_v19: requests.Session, token: str, since: str, until: str,
) -> list[dict]:
    print("\n" + "=" * 78)
    print("PASO 4 — Alternativas por cuenta (transactions v26/v19, campos de cuenta, activities)")
    print("=" * 78)

    v19_base = f"https://graph.facebook.com/{OLD_API_VERSION_FALLBACK}"
    all_charges: list[dict] = []

    for label, acc_id in TARGET_ACCOUNTS:
        print(f"\n  Cuenta: {label} (act_{acc_id})")

        r = _get(session_v26, f"{GRAPH_BASE_URL}/act_{acc_id}/transactions", {"limit": 200}, token)
        if r["ok"]:
            n = len(r["payload"].get("data", []))
            print(f"    /act_{acc_id}/transactions (v26.0): OK — {n} registro(s).")
        else:
            print(f"    /act_{acc_id}/transactions (v26.0): FALLÓ — {_fmt_error(r['error'])}")

        r = _get(session_v19, f"{v19_base}/act_{acc_id}/transactions", {"limit": 200}, token)
        if r["ok"]:
            n = len(r["payload"].get("data", []))
            print(f"    /act_{acc_id}/transactions ({OLD_API_VERSION_FALLBACK}): OK — {n} registro(s).")
        else:
            print(f"    /act_{acc_id}/transactions ({OLD_API_VERSION_FALLBACK}): FALLÓ — {_fmt_error(r['error'])}")

        r = _get(
            session_v26, f"{GRAPH_BASE_URL}/act_{acc_id}",
            {"fields": "amount_spent,balance,currency,account_status,funding_source_details"}, token,
        )
        if r["ok"]:
            print(f"    /act_{acc_id}?fields=amount_spent,balance,... : OK — {json.dumps(r['payload'], ensure_ascii=False)}")
        else:
            print(f"    /act_{acc_id}?fields=amount_spent,balance,... : FALLÓ — {_fmt_error(r['error'])}")

        records, error = fetch_all_activities(session_v26, acc_id, since, until, token)
        if error:
            print(f"    /act_{acc_id}/activities: FALLÓ — {_fmt_error(error)}")
            continue

        charges = extract_billing_charges(records)
        print(
            f"    /act_{acc_id}/activities: OK — {len(records)} evento(s) totales, "
            f"{len(charges)} de tipo 'ad_account_billing_charge' (cobros reales)."
        )
        if charges:
            print(f"      Primer cobro: {charges[0]}")
            for c in charges:
                c["account"] = label
            all_charges.extend(charges)

    if all_charges:
        (SCRATCH_DIR / "meta_activities_billing_charges.json").write_text(
            json.dumps(all_charges, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n  [info] {len(all_charges)} cobro(s) en total guardados en "
              f"{SCRATCH_DIR / 'meta_activities_billing_charges.json'}")

    return all_charges


# --- PASO 5: comparación contra CSV --------------------------------------

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def load_csv_monthly() -> pd.DataFrame:
    frames = []
    for path_str in CSV_PATHS:
        path = Path(path_str)
        if not path.exists():
            print(f"  [warn] CSV no encontrado, se ignora: {path}")
            continue
        try:
            frames.append(AdSpendLoader(str(path)).load())
            print(f"  [info] CSV leído: {path}")
        except Exception as exc:
            print(f"  [warn] No se pudo leer '{path}': {exc}")

    if not frames:
        return pd.DataFrame()
    combined = combine_ad_spend_sources(frames)
    return monthly_ad_spend_with_period(combined)


def charges_to_monthly(charges: list[dict]) -> pd.DataFrame:
    """Agrupa los cobros por mes, convirtiendo `event_time` (UTC, lo que
    devuelve la API) a `APP_TIMEZONE` (America/Bogota, la misma zona que ya
    usa el resto del proyecto) ANTES de extraer año/mes — confirmado
    empíricamente que el CSV de Facturación de Meta pone la fecha en la
    zona horaria LOCAL de la cuenta, no en UTC. Sin esta conversión, cobros
    hechos de madrugada UTC (tarde-noche en Bogotá) quedan un mes
    desalineados contra el CSV (ver ejemplo real: transacción
    23969853019372468-23910294425328331, event_time UTC "2025-07-01T03:58",
    CSV la fecha "30/06/2025" — mismo cobro, mes distinto sin esta
    conversión)."""
    if not charges:
        return pd.DataFrame(columns=["Año", "Mes_num", "Mes_Año", "Importe"])
    df = pd.DataFrame(charges)
    local = pd.to_datetime(df["event_time"]).dt.tz_convert(APP_TIMEZONE).dt.tz_localize(None)
    df["Año"] = local.dt.year
    df["Mes_num"] = local.dt.month
    df["Mes_Año"] = df["Mes_num"].map(MESES_ES) + " " + df["Año"].astype(str)
    grouped = df.groupby(["Año", "Mes_num", "Mes_Año"])["amount"].sum().reset_index()
    return grouped.rename(columns={"amount": "Importe"}).sort_values(["Año", "Mes_num"])


def step5_compare_against_csv(charges: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("PASO 5 — Comparación mensual API (/activities, cobros reales) vs CSV")
    print("=" * 78)

    csv_monthly = load_csv_monthly()
    if csv_monthly.empty:
        print("  [warn] No se pudo calcular el total mensual de los CSV — nada para comparar.")
        return

    if not charges:
        print(
            "\n  [warn] Ningún endpoint de la API devolvió cobros reales en este diagnóstico "
            "— no hay nada de la API para comparar contra los CSV."
        )
        print("\n  Totales mensuales SEGÚN LOS CSV (referencia/ground truth):")
        for _, row in csv_monthly.iterrows():
            print(f"    {row['Mes_Año']:18} ${row['Importe']:,.2f}")
        print(f"    {'TOTAL':18} ${csv_monthly['Importe'].sum():,.2f}")
        return

    api_monthly = charges_to_monthly(charges)
    csv_dict = dict(zip(csv_monthly["Mes_Año"], csv_monthly["Importe"]))
    api_dict = dict(zip(api_monthly["Mes_Año"], api_monthly["Importe"]))

    ordered_months: list[str] = []
    for m in list(csv_monthly["Mes_Año"]) + list(api_monthly["Mes_Año"]):
        if m not in ordered_months:
            ordered_months.append(m)

    header = f"{'Mes':18} | {'CSV ($)':>12} | {'API ($)':>12} | {'Diferencia':>12}"
    print(f"\n  (fechas de la API convertidas a {APP_TIMEZONE}, misma zona que el CSV)\n")
    print(f"  {header}")
    print("  " + "-" * len(header))
    for m in ordered_months:
        c, a = csv_dict.get(m), api_dict.get(m)
        c_str = f"{c:,.2f}" if c is not None else "—"
        a_str = f"{a:,.2f}" if a is not None else "—"
        diff_str = f"{(a - c):,.2f}" if (a is not None and c is not None) else "—"
        print(f"  {m:18} | {c_str:>12} | {a_str:>12} | {diff_str:>12}")

    print("  " + "-" * len(header))
    total_c, total_a = sum(csv_dict.values()), sum(api_dict.values())
    print(f"  {'TOTAL':18} | {total_c:>12,.2f} | {total_a:>12,.2f} | {(total_a - total_c):>12,.2f}")


# --- main -----------------------------------------------------------------

def main() -> None:
    if not META_ACCESS_TOKEN:
        raise DiagnosticError(
            "META_ACCESS_TOKEN no está configurado. Definilo en "
            ".streamlit/secrets.toml o en .env y volvé a correr este script."
        )

    SCRATCH_DIR.mkdir(exist_ok=True)
    session_v26 = _build_session(META_ACCESS_TOKEN)
    session_v19 = _build_session(META_ACCESS_TOKEN)

    step1_permissions(session_v26, META_ACCESS_TOKEN)
    owners = step2_find_account_owners(session_v26, META_ACCESS_TOKEN)

    business_ids = list({(o["business_name"], o["business_id"]) for o in owners.values()})
    if not business_ids:
        print(
            "\n[warn] No se identificó ningún negocio dueño de las 3 cuentas objetivo — "
            "se omite el paso 3 (business_invoices), no hay sobre qué negocio probarlo."
        )
    else:
        step3_business_invoices(session_v26, business_ids, META_ACCESS_TOKEN)

    since, until = "2025-01-01", pd.Timestamp.now().strftime("%Y-%m-%d")
    charges = step4_account_alternatives(session_v26, session_v19, META_ACCESS_TOKEN, since, until)
    step5_compare_against_csv(charges)

    print("\n" + "=" * 78)
    print("Fin del diagnóstico. Esto NO modificó nada en src/analytics/ ni src/ui/.")
    print(f"Archivos persistidos en {SCRATCH_DIR} (gitignored) para futuras sesiones.")
    print("=" * 78)


if __name__ == "__main__":
    try:
        main()
    except DiagnosticError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
