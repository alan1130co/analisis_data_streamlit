"""Tests de `src/data_sources/ai_provider.py` — todo con mocks (SDKs reales
de anthropic/openai, nunca llamadas de red reales):
- `get_ai_provider()` devuelve `None` sin API key (botón deshabilitado en
  la UI) y el adaptador correcto según `AI_PROVIDER`.
- Cada adaptador devuelve el texto de la respuesta simulada.
- La API key nunca aparece en el mensaje de `AIProviderError` cuando la
  llamada falla (ni el SDK, en su excepción, debería filtrarla al log).
- El adaptador de OpenAI reintenta sin `temperature` si la 1ra llamada
  falla mencionando ese parámetro (algunos modelos de razonamiento lo
  rechazan).
"""
import anthropic
import openai
import pytest

from src.data_sources.ai_provider import (
    AIProvider,
    AIProviderError,
    AnthropicProvider,
    OpenAIProvider,
    check_ai_connection,
    get_ai_provider,
)

API_KEY_SECRETA = "sk-ant-super-secreta-no-debe-aparecer-en-logs-123456"


# --- Dobles mínimos de los SDKs reales ---

class _FakeAnthropicTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeAnthropicMessage:
    def __init__(self, text):
        self.content = [_FakeAnthropicTextBlock(text)]


def _fake_anthropic_client(response_text=None, exc=None):
    llamadas = []

    class _Messages:
        def create(self, **kwargs):
            llamadas.append(kwargs)
            if exc is not None:
                raise exc
            return _FakeAnthropicMessage(response_text)

    class _Client:
        def __init__(self, **kwargs):
            self.init_kwargs = kwargs
            self.messages = _Messages()

    _Client.llamadas = llamadas
    return _Client


class _FakeOpenAIMessage:
    def __init__(self, content):
        self.content = content


class _FakeOpenAIChoice:
    def __init__(self, content):
        self.message = _FakeOpenAIMessage(content)


class _FakeOpenAIResponse:
    def __init__(self, content):
        self.choices = [_FakeOpenAIChoice(content)]


def _fake_openai_client(respuesta_final="ok", fallar_si_temperature=False, exc_siempre=None):
    llamadas = []

    class _Completions:
        def create(self, **kwargs):
            llamadas.append(kwargs)
            if exc_siempre is not None:
                raise exc_siempre
            if fallar_si_temperature and "temperature" in kwargs:
                raise Exception("Unsupported parameter: 'temperature' is not supported with this model.")
            return _FakeOpenAIResponse(respuesta_final)

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class _Client:
        def __init__(self, **kwargs):
            self.init_kwargs = kwargs
            self.chat = _Chat()

    _Client.llamadas = llamadas
    return _Client


# --- get_ai_provider() ---

def test_sin_api_key_devuelve_none():
    assert get_ai_provider(provider="anthropic", api_key="", model=None) is None


def test_con_api_key_provider_anthropic_devuelve_anthropic_provider():
    provider = get_ai_provider(provider="anthropic", api_key=API_KEY_SECRETA, model=None)
    assert isinstance(provider, AnthropicProvider)


def test_con_api_key_provider_openai_devuelve_openai_provider():
    provider = get_ai_provider(provider="openai", api_key=API_KEY_SECRETA, model=None)
    assert isinstance(provider, OpenAIProvider)


def test_provider_desconocido_cae_a_anthropic_por_defecto():
    provider = get_ai_provider(provider="no_existe", api_key=API_KEY_SECRETA, model=None)
    assert isinstance(provider, AnthropicProvider)


# --- AnthropicProvider ---

def test_anthropic_provider_generate_devuelve_texto(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic_client(response_text="Análisis simulado."))
    provider = AnthropicProvider(api_key=API_KEY_SECRETA)
    assert provider.generate("system", "user") == "Análisis simulado."


def test_anthropic_provider_error_no_filtra_api_key(monkeypatch):
    fake = _fake_anthropic_client(exc=Exception(f"Auth failed with key {API_KEY_SECRETA}"))
    monkeypatch.setattr(anthropic, "Anthropic", fake)
    provider = AnthropicProvider(api_key=API_KEY_SECRETA)
    with pytest.raises(AIProviderError) as exc_info:
        provider.generate("system", "user")
    assert API_KEY_SECRETA not in str(exc_info.value)
    assert "***" in str(exc_info.value)


# --- OpenAIProvider ---

def test_openai_provider_generate_devuelve_texto(monkeypatch):
    monkeypatch.setattr(openai, "OpenAI", _fake_openai_client(respuesta_final="Análisis de OpenAI."))
    provider = OpenAIProvider(api_key=API_KEY_SECRETA)
    assert provider.generate("system", "user") == "Análisis de OpenAI."


def test_openai_provider_error_no_filtra_api_key(monkeypatch):
    fake = _fake_openai_client(exc_siempre=Exception(f"Invalid key: {API_KEY_SECRETA}"))
    monkeypatch.setattr(openai, "OpenAI", fake)
    provider = OpenAIProvider(api_key=API_KEY_SECRETA)
    with pytest.raises(AIProviderError) as exc_info:
        provider.generate("system", "user")
    assert API_KEY_SECRETA not in str(exc_info.value)
    assert "***" in str(exc_info.value)


def test_openai_provider_modelo_no_reconocido_reintenta_sin_temperature(monkeypatch):
    """Fallback REACTIVO: un modelo que NO está en la lista conocida de
    "razonamiento" (`_is_openai_reasoning_model`) igual puede rechazar
    `temperature` — ahí sí vale la pena el reintento. Con un modelo
    reconocido (p.ej. el default `gpt-5-nano`) ya no hace falta: ver
    `test_openai_provider_reasoning_model_nunca_manda_temperature`."""
    fake = _fake_openai_client(respuesta_final="Respuesta tras reintento.", fallar_si_temperature=True)
    monkeypatch.setattr(openai, "OpenAI", fake)
    provider = OpenAIProvider(api_key=API_KEY_SECRETA, model="gpt-4.1-mini")

    texto = provider.generate("system", "user")

    assert texto == "Respuesta tras reintento."
    assert len(fake.llamadas) == 2
    assert "temperature" in fake.llamadas[0]
    assert "temperature" not in fake.llamadas[1]


def test_openai_provider_usa_max_completion_tokens_no_max_tokens(monkeypatch):
    fake = _fake_openai_client(respuesta_final="ok")
    monkeypatch.setattr(openai, "OpenAI", fake)
    provider = OpenAIProvider(api_key=API_KEY_SECRETA)
    provider.generate("system", "user")
    assert "max_completion_tokens" in fake.llamadas[0]
    assert "max_tokens" not in fake.llamadas[0]


def test_openai_provider_reasoning_model_nunca_manda_temperature(monkeypatch):
    """Regresión del bug reportado: `gpt-5-nano` (y el resto de la familia
    de razonamiento: gpt-5*/o1*/o3*/o4*) rechaza con 400 cualquier
    `temperature` distinto del default — antes se mandaba igual en el
    primer intento (desperdiciando una llamada) y, si la IA fallaba por
    otro motivo, el reintento sin verificar la causa real podía enmascarar
    el error de fondo. Ahora NUNCA se manda `temperature` para estos
    modelos, desde la primera llamada, y en cambio se manda
    `reasoning_effort` + un tope de tokens más alto."""
    fake = _fake_openai_client(respuesta_final="ok", fallar_si_temperature=True)
    monkeypatch.setattr(openai, "OpenAI", fake)
    provider = OpenAIProvider(api_key=API_KEY_SECRETA, model="gpt-5-nano")

    texto = provider.generate("system", "user")

    assert texto == "ok"
    assert len(fake.llamadas) == 1  # ni un reintento de más — nunca mandó temperature
    assert "temperature" not in fake.llamadas[0]
    assert fake.llamadas[0]["reasoning_effort"] == "low"
    assert fake.llamadas[0]["max_completion_tokens"] > 1024  # más margen que un modelo normal


def test_openai_provider_respuesta_vacia_de_modelo_de_razonamiento_lanza_error_claro(monkeypatch):
    """Root cause real del reporte sin análisis de IA: un modelo de
    razonamiento puede gastar TODO el presupuesto de `max_completion_tokens`
    pensando y devolver contenido vacío con `finish_reason="length"`, SIN
    lanzar ninguna excepción por sí solo — antes eso llegaba como texto
    vacío hasta el reporte final ("Análisis no disponible" sin ninguna
    pista). Ahora debe lanzar `AIProviderError` con un motivo legible."""
    class _ChoiceVacio:
        finish_reason = "length"

        class message:
            content = ""

    class _RespuestaVacia:
        choices = [_ChoiceVacio()]

    class _CompletionsVacias:
        def create(self, **kwargs):
            return _RespuestaVacia()

    class _ChatVacio:
        def __init__(self):
            self.completions = _CompletionsVacias()

    class _ClientVacio:
        def __init__(self, **kwargs):
            self.chat = _ChatVacio()

    monkeypatch.setattr(openai, "OpenAI", _ClientVacio)
    provider = OpenAIProvider(api_key=API_KEY_SECRETA, model="gpt-5-nano")

    with pytest.raises(AIProviderError, match="[Vv]ac"):
        provider.generate("system", "user")


# --- check_ai_connection() ---

class _FakeProviderOk(AIProvider):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "OK"


class _FakeProviderVacio(AIProvider):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "   "


class _FakeProviderFalla(AIProvider):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise AIProviderError("saldo insuficiente (insufficient_quota)")


def test_check_ai_connection_ok():
    ok, mensaje = check_ai_connection(_FakeProviderOk())
    assert ok is True
    assert "OK" in mensaje


def test_check_ai_connection_respuesta_vacia_es_error():
    ok, mensaje = check_ai_connection(_FakeProviderVacio())
    assert ok is False
    assert "vacío" in mensaje.lower()


def test_check_ai_connection_propaga_motivo_sanitizado_del_error():
    ok, mensaje = check_ai_connection(_FakeProviderFalla())
    assert ok is False
    assert "insufficient_quota" in mensaje
