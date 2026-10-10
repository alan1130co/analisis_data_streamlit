"""Proveedor de IA intercambiable para el análisis del reporte de Marketing
(ver `src/reports/report_orchestrator.py`). Interfaz común con 2
adaptadores (OpenAI y Anthropic) seleccionables por el secret `AI_PROVIDER`
— ver `src/config/settings.py`.

NO importa Streamlit — capa de datos pura (igual criterio que el resto de
`src/data_sources/`), aunque no hereda de `ContactsDataSource` (acá no se
cargan contactos, se genera texto a partir del payload agregado).

Modelos por defecto — elegidos por ser los más chicos/económicos vigentes
de cada proveedor para análisis de texto (no razonamiento complejo),
confirmados contra documentación oficial (ver reporte de la tarea):
  - Anthropic: Claude Haiku 4.5 — $1.00 / $5.00 por millón de tokens
    input/output.
  - OpenAI: gpt-5-nano — $0.05 / $0.40 por millón de tokens input/output.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.config.settings import AI_API_KEY, AI_MODEL, AI_PROVIDER

DEFAULT_MODEL_ANTHROPIC = "claude-haiku-4-5"
DEFAULT_MODEL_OPENAI = "gpt-5-nano"

# Temperatura baja (rango 0.2-0.3 pedido por negocio): respuestas
# consistentes y poco creativas — el análisis debe ceñirse a las cifras del
# payload, no "inventar" variaciones de redacción con cada llamada.
TEMPERATURE = 0.25
MAX_OUTPUT_TOKENS = 1024
REQUEST_TIMEOUT_SECONDS = 30.0
# Reintento a nivel de ESTE módulo (1, pedido por negocio) — además, cada
# SDK oficial ya reintenta internamente errores de red/429/5xx por su
# cuenta (`max_retries` del cliente), independiente de este contador.
MAX_RETRIES = 1

# Modelos de "razonamiento" de OpenAI (gpt-5*, o1*, o3*, o4*): 2
# diferencias confirmadas contra la API real (ver reporte de la tarea) que
# rompían el análisis en silencio:
#   1. Rechazan `temperature` distinto del default (1) — error 400
#      "Unsupported value: 'temperature' does not support 0.25...".
#   2. Gastan tokens de salida "pensando" (`reasoning_tokens`, cuentan
#      contra `max_completion_tokens`) ANTES de escribir la respuesta — con
#      el `MAX_OUTPUT_TOKENS` normal (1024) y el `reasoning_effort` por
#      defecto del modelo, el razonamiento solo podía consumir los 1024
#      tokens completos y devolver contenido VACÍO (`finish_reason`
#      "length", 0 caracteres de texto) sin lanzar ninguna excepción — el
#      análisis se veía "no disponible" sin ningún error visible.
# Fix: para estos modelos NO se manda `temperature` (se evita el 400 de
# entrada, sin gastar un reintento) y se manda `reasoning_effort="low"` +
# un tope de tokens mucho más alto (`MAX_OUTPUT_TOKENS_REASONING`) para que
# sobre presupuesto después de razonar.
_OPENAI_REASONING_MODEL_PREFIXES = ("gpt-5", "o1", "o3", "o4")
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS_REASONING = 4096


def _is_openai_reasoning_model(model: str) -> bool:
    return (model or "").strip().lower().startswith(_OPENAI_REASONING_MODEL_PREFIXES)


class AIProviderError(Exception):
    """Error de un adaptador de IA después de agotar los reintentos. El
    mensaje SIEMPRE pasa por `_sanitize_error` — la API key nunca debe
    llegar a logs, a la UI ni a este mensaje."""


def _sanitize_error(message: str, api_key: str) -> str:
    """Reemplaza cualquier aparición literal de la API key por '***'."""
    if api_key and api_key in message:
        return message.replace(api_key, "***")
    return message


class AIProvider(ABC):
    """Interfaz común: un adaptador por proveedor, un solo método público."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Devuelve el texto de respuesta del modelo. Lanza `AIProviderError`
        si la llamada falla después de reintentar — el caller (orquestador
        del reporte) debe capturarla y seguir con la siguiente sección, sin
        abortar el reporte completo."""
        ...

    def generate_with_usage(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        """Como `generate()`, pero además devuelve el uso REAL de tokens de
        ESTA llamada puntual (`{"input_tokens": int, "output_tokens": int}`)
        — usado por el orquestador (`src/reports/report_orchestrator.py`)
        para el costo real del reporte, sin estado compartido entre threads
        (cada llamada devuelve su propio uso, no un acumulador en `self`).
        Default: delega a `generate()` con uso en cero — un adaptador que no
        sobreescriba esto sigue generando el análisis igual, solo no aporta
        costo real medido."""
        return self.generate(system_prompt, user_prompt), {"input_tokens": 0, "output_tokens": 0}


class AnthropicProvider(AIProvider):
    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str | None = None):
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL_ANTHROPIC

    @property
    def model(self) -> str:
        return self._model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        texto, _usage = self.generate_with_usage(system_prompt, user_prompt)
        return texto

    def generate_with_usage(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        import anthropic

        client = anthropic.Anthropic(
            api_key=self._api_key,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=MAX_RETRIES,
        )
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            raise AIProviderError(_sanitize_error(str(exc), self._api_key)) from exc

        texto = "".join(block.text for block in response.content if block.type == "text")
        usage = getattr(response, "usage", None)
        usage_dict = (
            {
                "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            }
            if usage is not None
            else {"input_tokens": 0, "output_tokens": 0}
        )
        return texto, usage_dict


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def __init__(self, api_key: str, model: str | None = None):
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL_OPENAI

    @property
    def model(self) -> str:
        return self._model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        texto, _usage = self.generate_with_usage(system_prompt, user_prompt)
        return texto

    def generate_with_usage(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        import openai

        client = openai.OpenAI(
            api_key=self._api_key,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=MAX_RETRIES,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        es_razonamiento = _is_openai_reasoning_model(self._model)
        incluir_temperature = not es_razonamiento

        last_exc: Exception | None = None
        # 1 reintento propio (además del retry interno del SDK para 429/5xx):
        # si un modelo NO reconocido como "de razonamiento" (ver
        # `_is_openai_reasoning_model`) igual rechaza `temperature`, el
        # reintento la omite en vez de fallar directo.
        for attempt in range(MAX_RETRIES + 1):
            kwargs = dict(
                model=self._model,
                max_completion_tokens=MAX_OUTPUT_TOKENS_REASONING if es_razonamiento else MAX_OUTPUT_TOKENS,
                messages=messages,
            )
            if es_razonamiento:
                kwargs["reasoning_effort"] = REASONING_EFFORT
            if incluir_temperature:
                kwargs["temperature"] = TEMPERATURE
            try:
                response = client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                texto = choice.message.content or ""
                if not texto.strip():
                    # Modelo de razonamiento que gastó todo el presupuesto de
                    # tokens pensando y no dejó nada para la respuesta —
                    # nunca lanza excepción por sí solo, hay que detectarlo
                    # a mano (ver nota de `MAX_OUTPUT_TOKENS_REASONING`).
                    raise AIProviderError(_sanitize_error(
                        f"Respuesta vacía del modelo '{self._model}' "
                        f"(finish_reason='{choice.finish_reason}') — se agotaron los "
                        "tokens de salida, probablemente en razonamiento interno. "
                        "Subí MAX_OUTPUT_TOKENS_REASONING o bajá REASONING_EFFORT.",
                        self._api_key,
                    ))
                usage = getattr(response, "usage", None)
                usage_dict = (
                    {
                        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                    }
                    if usage is not None
                    else {"input_tokens": 0, "output_tokens": 0}
                )
                return texto, usage_dict
            except AIProviderError:
                raise
            except Exception as exc:
                last_exc = exc
                if incluir_temperature and "temperature" in str(exc).lower():
                    incluir_temperature = False
                    continue

        raise AIProviderError(_sanitize_error(str(last_exc), self._api_key)) from last_exc


# --- Costo estimado/real (ver src/reports/report_orchestrator.py) ---
# USD por millón de tokens (input, output) — mismos modelos/tarifas que los
# defaults de arriba (ver docstring de módulo para la fuente).
PRICING_USD_PER_MILLION_TOKENS: dict[str, dict[str, tuple[float, float]]] = {
    "anthropic": {DEFAULT_MODEL_ANTHROPIC: (1.00, 5.00)},
    "openai": {DEFAULT_MODEL_OPENAI: (0.05, 0.40)},
}

_DEFAULT_PRICING = (1.00, 5.00)  # fallback conservador si el modelo no está en la tabla


def get_pricing(provider: str, model: str) -> tuple[float, float]:
    tabla = PRICING_USD_PER_MILLION_TOKENS.get((provider or "").strip().lower(), {})
    return tabla.get(model, _DEFAULT_PRICING)


def estimate_tokens(text: str) -> int:
    """Estimación gruesa (sin tokenizer real, ~4 caracteres por token en
    español/inglés) — alcanza para un costo ESTIMADO antes de generar, no
    para facturación exacta (eso lo da el uso real de la API, ver
    `generate_with_usage`)."""
    return max(1, len(text) // 4)


def estimate_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    precio_input, precio_output = get_pricing(provider, model)
    return round(input_tokens / 1_000_000 * precio_input + output_tokens / 1_000_000 * precio_output, 4)


def get_ai_provider(
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> AIProvider | None:
    """Devuelve el adaptador configurado vía secrets (`AI_PROVIDER`/
    `AI_API_KEY`/`AI_MODEL`), o `None` si no hay API key configurada — el
    caller debe usar `None` para deshabilitar el botón "Generar reporte"
    (ver `src/ui/report_generator.py`, caption "Configura AI_API_KEY para
    generar el reporte")."""
    provider = (provider if provider is not None else AI_PROVIDER or "anthropic").strip().lower()
    api_key = api_key if api_key is not None else AI_API_KEY
    model = model if model is not None else (AI_MODEL or None)

    if not api_key:
        return None

    if provider == "openai":
        return OpenAIProvider(api_key, model)
    return AnthropicProvider(api_key, model)


def check_ai_connection(provider: AIProvider) -> tuple[bool, str]:
    """Llamada mínima para el botón "Probar conexión con la IA" (ver
    `src/ui/report_generator.py`) — antes de gastar las ~6 llamadas de un
    reporte completo, confirma rápido si el proveedor configurado
    (API key, modelo, proveedor) funciona. Devuelve `(ok, mensaje)` —
    `mensaje` siempre sanitizado, listo para mostrar en la UI (nunca
    expone la API key, viene de `AIProviderError`)."""
    try:
        texto = provider.generate(
            "Responde ÚNICAMENTE con la palabra OK, sin nada más.",
            "Probando la conexión.",
        )
    except AIProviderError as exc:
        return False, str(exc)

    if not texto.strip():
        return False, "La IA respondió vacío — revisá el límite de tokens de salida."
    return True, "Conexión con la IA OK."
