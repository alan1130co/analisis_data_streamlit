"""
Diagnóstico AISLADO del esquema real de la API de Clientify (Paso 2 del
plan de integración) — NO toca `src/analytics/` ni `src/ui/`, solo lee.

Objetivo: traer una muestra de contactos reales vía API y el catálogo
COMPLETO de custom fields, para confirmar empíricamente (no por hipótesis)
las 9 columnas de demografía/ubicación/atribución que quedaron sin mapear
en la auditoría de columnas del proyecto (`cumpleaños`, `nombre`, `ciudad 1`,
`provincia/estado 1`, `país`, `sector`, `Tipo de proceso`, `Campaña - pauta`,
`Publicacion por la que se contacto el cliente`).

2026-10 update: a diferencia de la versión anterior de este script, esta
persiste TODO lo que trae en `scratch/` (gitignored — ver `.gitignore`,
contiene datos reales de clientes) para que una sesión futura no dependa de
la memoria de esta conversación:
  - scratch/api_sample_contactos.json   — lista cruda de contactos de muestra
  - scratch/api_custom_fields_catalog.json — catálogo completo de custom fields

⚠️ AVISO IMPORTANTE — léase antes de correr esto:
No pude confirmar contra la documentación oficial de Clientify (
https://developer.clientify.com/ es una SPA en JavaScript que no expone su
contenido a una lectura automática) el contrato exacto de `/v1/contacts/` ni
de `/v1/custom-fields/`. Lo que ya se confirmó empíricamente en sesiones
anteriores de este proyecto (ver memoria + `diagnostic_api_auth_formats.py`):
paginación estilo DRF (`results`/`next`/`previous`) en `/contacts/`, con
`page_size` (no `limit`) controlando el tamaño de página; `/custom-fields/`
pagina distinto, con `?page=`. Este script asume eso pero maneja también el
caso de una respuesta en lista plana, por si cambia.

Uso:
    python scripts/diagnostic_api_schema.py
    python scripts/diagnostic_api_schema.py --sample-size 20
    python scripts/diagnostic_api_schema.py --base-url https://api.clientify.net/v2

Requiere CLIENTIFY_API_TOKEN configurado (en .streamlit/secrets.toml local,
o en .env) — se lee vía `src.config.settings._get_secret()`, igual que en
producción. No pega el token en ningún otro lado.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from src.config.settings import CLIENTIFY_API_TOKEN, CLIENTIFY_BASE_URL

SCRATCH_DIR = Path(__file__).parent.parent / "scratch"
SAMPLE_CONTACTS_PATH = SCRATCH_DIR / "api_sample_contactos.json"
CUSTOM_FIELDS_CATALOG_PATH = SCRATCH_DIR / "api_custom_fields_catalog.json"

# --- Las 30 columnas que hoy usa src/analytics/*.py, según la auditoría
# completa de columnas del proyecto (no solo las 21 del núcleo de
# embudo/cierres/valores que cubría la versión anterior de esta lista). ---
EXPECTED_COLUMNS = [
    # Núcleo embudo/cierres (ya mapeadas en ClientifyAPIClient)
    "creado",
    "propietario",
    "estado",
    "canal online",
    "Canal offline",
    "Origen de la pauta",
    "Etiquetas",
    "Motivo de no cierre",
    "Cantidad de cierres",
    "Fecha de cierre",
    "Fecha de segundo cierre",
    "Fecha de tercer cierre",
    "Fecha de 4to cierre",
    "Valor total del proceso",
    "Valor total segundo cierre",
    "Valor total tercer cierre",
    "Valor total 4to cierre",
    "Cuota inicial pactada",
    "Cuota inicial segundo cierre",
    "Cuota inicial tercer cierre",
    "Cuota inicial 4to cierre",
    # Demografía / ubicación / atribución (sin mapear — objeto de este diagnóstico)
    "cumpleaños",
    "nombre",
    "ciudad 1",
    "provincia/estado 1",
    "país",
    "sector",
    "Tipo de proceso",
    "Campaña - pauta",
    "Publicacion por la que se contacto el cliente",
]


class DiagnosticError(RuntimeError):
    """Error claro y accionable, para no mostrar un traceback genérico."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-size", type=int, default=20, help="Contactos a traer (máx. 50, default 20)")
    parser.add_argument("--base-url", default=CLIENTIFY_BASE_URL, help="Base URL de la API (default: settings.CLIENTIFY_BASE_URL)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout por request en segundos (default 30)")
    parser.add_argument(
        "--skip-catalog", action="store_true",
        help="No traer el catálogo de custom fields (solo contactos de muestra).",
    )
    return parser.parse_args()


def build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    })
    return session


def safe_get(session: requests.Session, url: str, *, params: dict | None = None, timeout: int = 30) -> dict:
    """GET con manejo de errores claro — nunca deja pasar un traceback genérico."""
    try:
        resp = session.get(url, params=params, timeout=timeout)
    except requests.exceptions.ConnectTimeout:
        raise DiagnosticError(f"Timeout conectando a {url}. Revisá tu conexión o CLIENTIFY_BASE_URL.")
    except requests.exceptions.ConnectionError as exc:
        raise DiagnosticError(f"No se pudo conectar a {url} ({exc}). ¿CLIENTIFY_BASE_URL está bien escrito?")
    except requests.exceptions.RequestException as exc:
        raise DiagnosticError(f"Error de red llamando a {url}: {exc}")

    if resp.status_code == 401:
        raise DiagnosticError(
            f"401 Unauthorized en {url}. CLIENTIFY_API_TOKEN no es válido o expiró. "
            "Revisá el valor en .streamlit/secrets.toml o .env."
        )
    if resp.status_code == 403:
        raise DiagnosticError(
            f"403 Forbidden en {url}. El token es válido pero la cuenta no tiene permiso para este endpoint."
        )
    if resp.status_code == 404:
        raise DiagnosticError(
            f"404 Not Found en {url}. La ruta no existe en esta base URL/versión — "
            "probá con --base-url (p.ej. .../v1 vs .../v2)."
        )
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "desconocido")
        raise DiagnosticError(
            f"429 Too Many Requests en {url}. Rate limit alcanzado — esperá "
            f"{retry_after} segundos y volvé a intentar con --sample-size más chico."
        )
    if not resp.ok:
        raise DiagnosticError(f"HTTP {resp.status_code} inesperado en {url}: {resp.text[:500]}")

    try:
        return resp.json()
    except ValueError:
        raise DiagnosticError(f"La respuesta de {url} no es JSON válido:\n{resp.text[:500]}")


def fetch_sample_contacts(session: requests.Session, base_url: str, n: int, timeout: int) -> list[dict]:
    """Trae hasta `n` contactos reales, paginando con `page_size` (confirmado
    empíricamente en 2026-09-30b — no `limit`, que esta cuenta ignora)."""
    url = f"{base_url.rstrip('/')}/contacts/"
    contacts: list[dict] = []
    params = {"page_size": min(n, 250)}
    while url and len(contacts) < n:
        payload = safe_get(session, url, params=params, timeout=timeout)
        if isinstance(payload, dict) and "results" in payload:
            contacts.extend(payload["results"])
            print(f"[info] Página recibida: {len(payload['results'])} contactos "
                  f"(acumulado {len(contacts)}, count total={payload.get('count', '?')}).")
            url = payload.get("next")
            params = None  # 'next' ya trae los params codificados
        elif isinstance(payload, list):
            contacts.extend(payload)
            print(f"[info] Respuesta en lista plana: {len(payload)} contactos.")
            url = None
        else:
            raise DiagnosticError(
                f"No reconozco la forma de la respuesta de {url} (ni dict con 'results' ni lista). "
                f"Claves recibidas: {list(payload.keys()) if isinstance(payload, dict) else type(payload)}"
            )

    if not contacts:
        raise DiagnosticError(f"{base_url}/contacts/ respondió 0 contactos. ¿La cuenta tiene contactos cargados?")

    return contacts[:n]


def fetch_custom_fields_catalog(session: requests.Session, base_url: str, timeout: int) -> list[dict]:
    """Trae el catálogo COMPLETO de custom fields (`GET /v1/custom-fields/`),
    paginado con `?page=` (confirmado en la memoria del proyecto — este
    endpoint pagina distinto a `/contacts/`, no usa `page_size`/`results`
    necesariamente de la misma forma, así que se maneja de forma defensiva)."""
    url = f"{base_url.rstrip('/')}/custom-fields/"
    all_fields: list[dict] = []
    params: dict | None = {"page": 1}
    page_num = 1
    while url:
        payload = safe_get(session, url, params=params, timeout=timeout)
        if isinstance(payload, dict) and "results" in payload:
            all_fields.extend(payload["results"])
            print(f"[info] Catálogo custom-fields, página {page_num}: {len(payload['results'])} campos "
                  f"(acumulado {len(all_fields)}, count total={payload.get('count', '?')}).")
            next_url = payload.get("next")
            if next_url:
                url = next_url
                params = None  # 'next' ya trae los params codificados
                page_num += 1
            else:
                url = None
        elif isinstance(payload, list):
            all_fields.extend(payload)
            print(f"[info] Catálogo custom-fields en lista plana: {len(payload)} campos.")
            url = None
        else:
            raise DiagnosticError(
                f"No reconozco la forma de la respuesta de {url} (ni dict con 'results' ni lista). "
                f"Claves recibidas: {list(payload.keys()) if isinstance(payload, dict) else type(payload)}"
            )
    return all_fields


# --- Matching heurístico para la tabla comparativa (ayuda-memoria, no verdad absoluta) ---

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in text.lower() if ch.isalnum())


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Aplana dicts/listas anidadas a un solo nivel `ruta.a.campo -> valor`,
    incluyendo pares tipo [{"name": "...", "value": "..."}] (forma típica de
    custom fields en varias APIs) indexados también por su `name`/`label`.
    """
    flat: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            flat.update(flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, dict) and any(k in item for k in ("name", "label", "key", "field")):
                label = item.get("name") or item.get("label") or item.get("key") or item.get("field")
                value = item.get("value", item.get("field_value", item))
                flat[f"{prefix}[{label}]"] = value
            else:
                flat.update(flatten(item, f"{prefix}[{i}]"))
    else:
        flat[prefix] = obj
    return flat


def find_match(expected: str, flat_keys: dict[str, Any]) -> tuple[str | None, Any]:
    """Heurístico de coincidencia por nombre normalizado. Exige longitud
    mínima en AMBOS lados antes de aceptar una coincidencia por substring
    (no solo en `expected`) — de lo contrario, claves nativas cortas como
    "id" matchean por accidente contra cualquier palabra larga que las
    contenga (p.ej. "id" dentro de "cant-id-ad de cierres").
    """
    target = _normalize(expected)
    MIN_LEN = 5
    for key, value in flat_keys.items():
        candidate = _normalize(key.rsplit(".", 1)[-1].split("[")[-1].rstrip("]") if "[" in key else key)
        if candidate == target:
            return key, value
        if len(target) >= MIN_LEN and len(candidate) >= MIN_LEN and (target in candidate or candidate in target):
            return key, value
    return None, None


def print_comparison_table(sample_contact: dict) -> None:
    print("\n" + "=" * 78)
    print("Comparación (1er contacto de la muestra): columnas esperadas vs campos reales")
    print("=" * 78)
    print(
        "(heurístico por coincidencia de nombre normalizado — la sección de "
        "análisis dirigido más abajo es la fuente de verdad, esta tabla es solo un vistazo rápido)\n"
    )

    flat = flatten(sample_contact)
    header = f"{'Columna esperada':47} | {'Campo API encontrado':35} | {'Tipo':10} | Valor de muestra"
    print(header)
    print("-" * len(header))

    for col in EXPECTED_COLUMNS:
        key, value = find_match(col, flat)
        if key is None:
            print(f"{col:47} | {'NO ENCONTRADO':35} | {'-':10} | -")
            continue
        tipo = "custom" if "[" in key else "nativo"
        valor = str(value)
        if len(valor) > 40:
            valor = valor[:37] + "..."
        print(f"{col:47} | {key:35} | {tipo:10} | {valor}")


# --- Análisis dirigido a las 9 columnas sin confirmar (sección 3 del pedido) ---

_TARGET_TERMS = {
    "sector": ["sector"],
    "Campaña - pauta / Campaña": ["campana", "campaign"],
    "Publicacion por la que se contacto el cliente": ["publicacion", "publicac"],
    "Tipo de proceso": ["tipodeproceso", "tipo de proceso", "tipoproceso"],
}


def analyze_birthday(contacts: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("1. ¿Existe 'birthday' a nivel raíz?")
    print("=" * 78)
    present = sum(1 for c in contacts if "birthday" in c)
    populated = sum(1 for c in contacts if c.get("birthday"))
    print(f"  Contactos con la clave 'birthday' presente: {present}/{len(contacts)}")
    print(f"  Contactos con 'birthday' POBLADO (no null/''): {populated}/{len(contacts)}")
    ejemplos = [c.get("birthday") for c in contacts if c.get("birthday")][:5]
    print(f"  Ejemplos de valor: {ejemplos}")


def analyze_name_fields(contacts: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("2. ¿Cómo se llama el campo de nombre?")
    print("=" * 78)
    candidatos = ["first_name", "last_name", "name", "full_name", "display_name"]
    for campo in candidatos:
        present = sum(1 for c in contacts if campo in c)
        populated = sum(1 for c in contacts if c.get(campo))
        ejemplos = [c.get(campo) for c in contacts if c.get(campo)][:3]
        print(f"  '{campo}': presente en {present}/{len(contacts)}, poblado en {populated}/{len(contacts)}, ejemplos={ejemplos}")


def analyze_addresses(contacts: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("3. ¿Existe el array 'addresses'? ¿city/state/country consistentes? ¿más de 1 elemento?")
    print("=" * 78)
    con_key = [c for c in contacts if "addresses" in c]
    print(f"  Contactos con la clave 'addresses' presente: {len(con_key)}/{len(contacts)}")
    no_vacios = [c for c in con_key if c.get("addresses")]
    print(f"  Contactos con 'addresses' NO vacío (>=1 elemento): {len(no_vacios)}/{len(contacts)}")
    longitudes = [len(c.get("addresses") or []) for c in con_key]
    if longitudes:
        print(f"  Distribución de longitud del array: min={min(longitudes)}, max={max(longitudes)}, "
              f"contactos con >1 elemento: {sum(1 for l in longitudes if l > 1)}")
    city_count = state_count = country_count = postal_count = 0
    ejemplo_addr = None
    for c in no_vacios:
        addr0 = (c.get("addresses") or [{}])[0]
        if not isinstance(addr0, dict):
            continue
        if ejemplo_addr is None:
            ejemplo_addr = addr0
        if addr0.get("city"):
            city_count += 1
        if addr0.get("state"):
            state_count += 1
        if addr0.get("country"):
            country_count += 1
        if addr0.get("postal_code"):
            postal_count += 1
    print(f"  De los {len(no_vacios)} con addresses no vacío, en addresses[0]:")
    print(f"    city poblado: {city_count}, state poblado: {state_count}, "
          f"country poblado: {country_count}, postal_code poblado: {postal_count}")
    print(f"  Ejemplo de addresses[0] completo: {json.dumps(ejemplo_addr, ensure_ascii=False)}")


def analyze_custom_fields_catalog(catalog: list[dict]) -> None:
    print("\n" + "=" * 78)
    print(f"4. Catálogo de custom fields ({len(catalog)} campos) — búsqueda dirigida")
    print("=" * 78)
    if not catalog:
        print("  [warn] Catálogo vacío o no se pudo traer (ver --skip-catalog / errores arriba).")
        return

    print("  Catálogo completo (nombre | tipo | id):")
    for field in catalog:
        nombre = field.get("name") or field.get("label") or field.get("field") or "?"
        tipo = field.get("field_type") or field.get("type") or "?"
        fid = field.get("id") or field.get("pk") or "?"
        print(f"    - {nombre!r:55} tipo={tipo!r:20} id={fid}")

    print("\n  Coincidencias para los términos buscados:")
    for etiqueta, terms in _TARGET_TERMS.items():
        matches = []
        for field in catalog:
            nombre = str(field.get("name") or field.get("label") or field.get("field") or "")
            norm = _normalize(nombre)
            if any(_normalize(t) in norm for t in terms):
                matches.append(nombre)
        if matches:
            print(f"    '{etiqueta}': COINCIDE con {matches}")
        else:
            print(f"    '{etiqueta}': sin coincidencia en el catálogo")


def main() -> None:
    args = parse_args()
    sample_size = max(1, min(args.sample_size, 50))

    if not CLIENTIFY_API_TOKEN:
        raise DiagnosticError(
            "CLIENTIFY_API_TOKEN no está configurado. Definilo en "
            ".streamlit/secrets.toml (local, copiando secrets.toml.example) "
            "o en .env, y volvé a correr este script."
        )

    SCRATCH_DIR.mkdir(exist_ok=True)

    print(f"[info] Base URL: {args.base_url}")
    print(f"[info] Trayendo {sample_size} contacto(s) de muestra...\n")

    session = build_session(CLIENTIFY_API_TOKEN)

    print("=" * 78)
    print("PASO 1 — muestra de contactos reales")
    print("=" * 78)
    contacts = fetch_sample_contacts(session, args.base_url, sample_size, args.timeout)
    print(f"[info] {len(contacts)} contacto(s) recibido(s).")

    SAMPLE_CONTACTS_PATH.write_text(
        json.dumps(contacts, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[info] Muestra completa guardada en {SAMPLE_CONTACTS_PATH}")

    catalog: list[dict] = []
    if not args.skip_catalog:
        print("\n" + "=" * 78)
        print("PASO 2 — catálogo completo de custom fields (GET /v1/custom-fields/)")
        print("=" * 78)
        try:
            catalog = fetch_custom_fields_catalog(session, args.base_url, args.timeout)
            CUSTOM_FIELDS_CATALOG_PATH.write_text(
                json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"[info] Catálogo completo ({len(catalog)} campos) guardado en {CUSTOM_FIELDS_CATALOG_PATH}")
        except DiagnosticError as exc:
            print(f"[warn] No se pudo traer el catálogo de custom fields: {exc}")

    print_comparison_table(contacts[0])

    analyze_birthday(contacts)
    analyze_name_fields(contacts)
    analyze_addresses(contacts)
    analyze_custom_fields_catalog(catalog)

    print("\n" + "=" * 78)
    print("Fin del diagnóstico. Esto NO modificó nada en el proyecto ni implementó el loader.")
    print(f"Archivos persistidos en {SCRATCH_DIR} (gitignored) para futuras sesiones.")
    print("=" * 78)


if __name__ == "__main__":
    try:
        main()
    except DiagnosticError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
