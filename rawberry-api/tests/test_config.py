import os

from app.config import Settings


def test_settings_reads_environment_values(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-east1")
    monkeypatch.setenv("USE_MOCK_CHAT", "false")

    settings = Settings.from_env()

    assert settings.google_cloud_project == "demo-project"
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.google_cloud_location == "us-east1"
    assert settings.use_mock_chat is False


def test_settings_defaults_to_mock_chat(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_ID", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("USE_MOCK_CHAT", raising=False)

    settings = Settings.from_env()

    assert settings.google_cloud_project is None
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.google_cloud_location == "global"
    assert settings.use_mock_chat is True
