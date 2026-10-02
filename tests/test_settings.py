from src.config import settings


def test_get_secret_usa_st_secrets_si_esta_presente(monkeypatch):
    monkeypatch.setattr(settings.st, "secrets", {"CLIENTIFY_API_TOKEN": "token-de-secrets"})
    monkeypatch.setenv("CLIENTIFY_API_TOKEN", "token-de-env")

    assert settings._get_secret("CLIENTIFY_API_TOKEN") == "token-de-secrets"


def test_get_secret_cae_a_env_var_si_falta_la_clave_en_st_secrets(monkeypatch):
    monkeypatch.setattr(settings.st, "secrets", {})
    monkeypatch.setenv("CLIENTIFY_API_TOKEN", "token-de-env")

    assert settings._get_secret("CLIENTIFY_API_TOKEN") == "token-de-env"


def test_get_secret_cae_a_env_var_si_no_existe_secrets_toml(monkeypatch):
    class _NoSecretsFile:
        def __getitem__(self, key):
            raise FileNotFoundError("No secrets files found")

    monkeypatch.setattr(settings.st, "secrets", _NoSecretsFile())
    monkeypatch.setenv("CLIENTIFY_API_TOKEN", "token-de-env")

    assert settings._get_secret("CLIENTIFY_API_TOKEN") == "token-de-env"


def test_get_secret_devuelve_default_sin_lanzar_si_no_hay_nada_configurado(monkeypatch):
    monkeypatch.setattr(settings.st, "secrets", {})
    monkeypatch.delenv("CLIENTIFY_API_TOKEN", raising=False)

    assert settings._get_secret("CLIENTIFY_API_TOKEN", "") == ""


def test_get_secret_ignora_valor_vacio_en_st_secrets_y_cae_a_env(monkeypatch):
    monkeypatch.setattr(settings.st, "secrets", {"CLIENTIFY_API_TOKEN": ""})
    monkeypatch.setenv("CLIENTIFY_API_TOKEN", "token-de-env")

    assert settings._get_secret("CLIENTIFY_API_TOKEN") == "token-de-env"
