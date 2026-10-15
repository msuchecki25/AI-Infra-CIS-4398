import pytest


@pytest.fixture(autouse=True)
def isolate_application_database(monkeypatch):
    """Ordinary tests must not inherit a developer's application database."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
