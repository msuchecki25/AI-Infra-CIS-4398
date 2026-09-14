import os

from app.config import Settings


def test_settings_reads_environment_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setenv("GEMINI_API_BASE_URL", "https://example.test")
    monkeypatch.setenv("USE_MOCK_CHAT", "false")

    settings = Settings.from_env()

    assert settings.gemini_api_key == "test-key"
    assert settings.gemini_model == "gemini-2.0-flash"
    assert settings.gemini_api_base_url == "https://example.test"
    assert settings.use_mock_chat is False


def test_settings_defaults_to_mock_chat(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_BASE_URL", raising=False)
    monkeypatch.delenv("USE_MOCK_CHAT", raising=False)

    settings = Settings.from_env()

    assert settings.gemini_api_key is None
    assert settings.gemini_model == "gemini-2.0-flash"
    assert settings.gemini_api_base_url == "https://generativelanguage.googleapis.com"
    assert settings.use_mock_chat is True
