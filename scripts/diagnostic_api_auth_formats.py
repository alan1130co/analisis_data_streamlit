"""
Diagnóstico AISLADO de formato de autenticación de la API de Clientify.

Contexto: `scripts/diagnostic_api_schema.py` devuelve 401 Unauthorized
contra GET /v1/contacts/ usando `Authorization: Token <token>`, incluso con
el token copiado directo desde el panel de Clientify (ícono del ojo, sin
espacios). Como no pudimos confirmar el formato de auth exacto desde
developer.clientify.com (SPA en JS, no legible por fetch automático), este
script prueba EMPÍRICAMENTE 5 formatos distintos contra el mismo endpoint
real, uno por uno, y reporta qué código HTTP devuelve cada uno.

No toca `src/analytics/` ni `src/ui/`. No implementa el loader. Es de un
solo uso — sirve para decidir qué header usar en `ClientifyAPIClient`
(Paso 3), o para concluir que el problema está en el token mismo, no en el
formato del header.

Uso:
    python scripts/diagnostic_api_auth_formats.py
    python scripts/diagnostic_api_auth_formats.py --url https://api.clientify.net/v1/contacts/

Requiere CLIENTIFY_API_TOKEN en .streamlit/secrets.toml o .env (vía
`src.config.settings`, igual que el resto del proyecto). El token nunca se
imprime completo en la salida (se enmascara), solo el resultado del intento.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from src.config.settings import CLIENTIFY_API_TOKEN, CLIENTIFY_BASE_URL

DEFAULT_URL = f"{CLIENTIFY_BASE_URL.rstrip('/')}/contacts/"

# Placeholders conocidos de este repo (.env.example / secrets.toml.example) —
# si el token cargado es literalmente uno de estos, ni vale la pena pegarle
# a la API real: el problema no es el formato del header.
PLACEHOLDER_VALUES = {"tu_token_aqui"}


def mask(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


def build_attempts(token: str, url: str) -> list[dict]:
    """Cada intento es independiente: headers propios y/o query params
    propios, sin mezclar formatos entre sí."""
    return [
        {
            "label": "1. Authorization: Bearer <token>",
            "headers": {"Authorization": f"Bearer {token}"},
            "params": {},
        },
        {
            "label": "2. Authorization: Token <token>",
            "headers": {"Authorization": f"Token {token}"},
            "params": {},
        },
        {
            "label": "3. Api-Token: <token>",
            "headers": {"Api-Token": token},
            "params": {},
        },
        {
            "label": "4. X-Api-Key: <token>",
            "headers": {"X-Api-Key": token},
            "params": {},
        },
        {
            "label": "5a. query param ?api_key=<token>",
            "headers": {},
            "params": {"api_key": token},
        },
        {
            "label": "5b. query param ?token=<token>",
            "headers": {},
            "params": {"token": token},
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Endpoint a probar (default: {DEFAULT_URL})")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    if not CLIENTIFY_API_TOKEN:
        print(
            "[ERROR] CLIENTIFY_API_TOKEN no está configurado en .streamlit/secrets.toml ni en .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    if CLIENTIFY_API_TOKEN in PLACEHOLDER_VALUES:
        print(
            f"[ERROR] CLIENTIFY_API_TOKEN todavía tiene el valor de placeholder "
            f"('{CLIENTIFY_API_TOKEN}', tomado de .env.example / secrets.toml.example) — "
            "no es un token real. Reemplazalo en .streamlit/secrets.toml (o .env) por el "
            "token copiado del panel de Clientify y volvé a correr este script.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"URL de prueba: {args.url}")
    print(f"Token usado (enmascarado): {mask(CLIENTIFY_API_TOKEN)}  (longitud: {len(CLIENTIFY_API_TOKEN)})")

    attempts = build_attempts(CLIENTIFY_API_TOKEN, args.url)
    results = []
    for attempt in attempts:
        try:
            resp = requests.get(
                args.url,
                headers={"Content-Type": "application/json", **attempt["headers"]},
                params=attempt["params"],
                timeout=args.timeout,
            )
            status = resp.status_code
        except requests.exceptions.RequestException as exc:
            print(f"\n--- {attempt['label']} ---\n  ERROR DE RED: {exc}")
            results.append((attempt["label"], "ERROR"))
            continue

        print(f"\n--- {attempt['label']} ---")
        print(f"  HTTP {status}")
        if status != 401:
            print(f"  Cuerpo (primeros 500 chars): {resp.text[:500]}")
        results.append((attempt["label"], status))

    print("\n" + "=" * 78)
    print("RESUMEN")
    print("=" * 78)
    # Éxito real = 2xx únicamente. Ojo: esta API responde 404 con cuerpo
    # {"detail":"Api key not provided."} cuando el mecanismo de auth ni
    # siquiera se reconoce — eso sigue siendo un FALLO, no un 404 genérico
    # de "ruta inexistente". No lo cuentes como éxito solo por no ser 401/403.
    any_success = False
    for label, status in results:
        is_success = isinstance(status, int) and 200 <= status < 300
        marker = "<-- funcionó" if is_success else ""
        print(f"  {label:45} -> {status} {marker}")
        if is_success:
            any_success = True

    if not any_success:
        print(
            "\n[CONCLUSIÓN] Ningún formato de autenticación probado devolvió 2xx. Con 6 formatos "
            "distintos fallando, lo más probable ya NO es el formato del header, sino el token en "
            "sí. Verificá directamente en el panel de Clientify:\n"
            "  - Que el token esté ACTIVO (no revocado/expirado).\n"
            "  - Que la cuenta/usuario que generó el token tenga permisos de API habilitados "
            "(a veces es un toggle separado del plan, no solo de generar el token).\n"
            "  - Que no sea un token de un ambiente distinto (sandbox/staging) apuntando a la "
            "URL de producción, o viceversa.\n"
            "  - Que la URL base sea la correcta para tu cuenta (algunas integraciones de "
            "Clientify usan un subdominio o versión distinta a /v1/ — confirmalo en el panel).\n"
            "  Puede valer la pena regenerar el token desde cero y volver a probar."
        )
    else:
        print("\n[CONCLUSIÓN] Al menos un formato funcionó — usá ese en ClientifyAPIClient (Paso 3).")


if __name__ == "__main__":
    main()
