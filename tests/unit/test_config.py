"""Unit tests: settings loading from environment."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.app_name == "pramya"
    assert settings.api_prefix == "/api/v1"
    assert settings.upload_max_mb == 5
    assert settings.voice_retention_days == 30


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    settings = Settings(_env_file=None)
    assert settings.app_env == "test"
    assert settings.deepseek_model == "deepseek-v4-flash"


def test_invalid_port_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_port=-1, _env_file=None)


def test_get_settings_cached() -> None:
    assert get_settings() is get_settings()
