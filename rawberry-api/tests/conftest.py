import pytest


@pytest.fixture(autouse=True)
def isolate_application_database(monkeypatch):
    """Ordinary tests must not inherit a developer's application database."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("USE_MOCK_CHAT", "true")


@pytest.fixture(autouse=True)
def developer_upload_credentials(monkeypatch):
    monkeypatch.setenv("DEVELOPER_UPLOAD_API_KEY", "test-upload-key")
