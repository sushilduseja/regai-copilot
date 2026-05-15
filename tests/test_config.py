import pytest
from pydantic import ValidationError
from regai.config import Settings, ProductionConfigError


def test_config_defaults_dev():
    settings = Settings()
    assert settings.environment == "development"
    assert settings.data_dir == "./data"
    assert settings.database_url == "sqlite:///data/regai.db"
    assert settings.log_level == "info"


def test_config_overrides_from_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("DATA_DIR", "/tmp/regai")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/regai.db")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings()
    assert settings.environment == "staging"
    assert settings.data_dir == "/tmp/regai"
    assert settings.database_url == "sqlite:////tmp/regai.db"
    assert settings.log_level == "debug"


def test_production_fails_without_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("WORKOS_CLIENT_ID", "")
    monkeypatch.setenv("WORKOS_API_KEY", "")
    monkeypatch.setenv("PINECONE_API_KEY", "")
    monkeypatch.setenv("SECRET_KEY", "change-me")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    with pytest.raises((ValidationError, ProductionConfigError)) as exc_info:
        Settings()

    assert "Production requires" in str(exc_info.value)


def test_production_fails_short_secret_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("WORKOS_CLIENT_ID", "client_123")
    monkeypatch.setenv("WORKOS_API_KEY", "sk_test_123")
    monkeypatch.setenv("WORKOS_REDIRECT_URI", "https://app.example.com/auth/callback")
    monkeypatch.setenv("PINECONE_API_KEY", "pc_123")
    monkeypatch.setenv("SECRET_KEY", "short")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_123")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/regai.db")

    with pytest.raises((ValidationError, ProductionConfigError)) as exc_info:
        Settings()

    assert "SECRET_KEY" in str(exc_info.value)
