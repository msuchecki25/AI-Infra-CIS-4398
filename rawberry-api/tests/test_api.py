from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_create_app_uses_isolated_storage():
    first_app = create_app()
    second_app = create_app()

    first_store = first_app.state.store
    second_store = second_app.state.store

    assert first_store is not second_store

    first_store.add({"id": "one", "text": "alpha", "metadata": {}})
    assert len(first_store.list_items()) == 1
    assert len(second_store.list_items()) == 0


def test_root_has_typed_contract():
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "RAWBerry API is running"
    assert "/health" in payload["available_endpoints"]


def test_health_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ingest_and_get_round_trip():
    app = create_app()
    client = TestClient(app)

    ingest_response = client.post(
        "/ingest",
        json={"userid": 1, "text": "hello world", "metadata": {"source": "demo"}},
    )

    assert ingest_response.status_code == 201
    payload = ingest_response.json()
    assert payload["message"] == "Item ingested successfully"
    assert payload["item"]["text"] == "hello world"
    assert payload["count"] == 1

    get_response = client.get("/get")
    assert get_response.status_code == 200
    assert get_response.json()["count"] == 1


def test_chat_uses_typed_reply(monkeypatch):
    monkeypatch.setenv("USE_MOCK_CHAT", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_ID", raising=False)

    app = create_app()
    client = TestClient(app)
    client.post(
        "/ingest",
        json={"userid": 1, "text": "first item"},
    )

    response = client.post(
        "/chat",
        json={
            "userid": 1,
            "data": {"window": 3, "agent": "test"},
            "message": "hello",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "You said: hello"
    assert len(payload["recent_items"]) == 1


def test_system_prompt_can_be_read_updated_and_cleared():
    client = TestClient(create_app())

    initial = client.get("/users/42/system-prompt")
    assert initial.status_code == 200
    assert initial.json() == {"userid": 42, "prompt": ""}

    updated = client.put("/users/42/system-prompt", json={"prompt": "Be concise."})
    assert updated.status_code == 200
    assert updated.json() == {"userid": 42, "prompt": "Be concise."}
    assert client.get("/users/43/system-prompt").json()["prompt"] == ""

    cleared = client.put("/users/42/system-prompt", json={"prompt": ""})
    assert cleared.status_code == 200
    assert cleared.json()["prompt"] == ""


def test_system_prompt_rejects_values_over_limit():
    client = TestClient(create_app())

    response = client.put("/users/42/system-prompt", json={"prompt": "x" * 2001})

    assert response.status_code == 422


def test_chat_includes_saved_user_system_prompt():
    client = TestClient(create_app())
    client.put("/users/42/system-prompt", json={"prompt": "Be concise."})

    response = client.post(
        "/chat",
        json={
            "userid": 42,
            "data": {"window": 3, "agent": "test"},
            "message": "Explain this.",
        },
    )

    assert response.status_code == 200
    assert "Be concise." in response.json()["reply"]
    assert "Explain this." in response.json()["reply"]


def test_invalid_message_is_rejected():
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/chat",
        json={
            "userid": 1,
            "data": {"window": 3, "agent": "test"},
            "message": "",
        },
    )
    assert response.status_code == 422


def test_chat_route_uses_mock_fallback_when_disabled(monkeypatch):
    monkeypatch.setenv("USE_MOCK_CHAT", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "userid": 1,
            "data": {"window": 3, "agent": "test"},
            "message": "fallback check",
        },
    )
    assert response.status_code == 200
    assert response.json()["reply"] == "You said: fallback check"


def test_chat_route_uses_configured_gemini_client(monkeypatch):
    monkeypatch.setenv("USE_MOCK_CHAT", "false")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")

    from app.services import chat_service as chat_service_module

    fake_llm = MagicMock()
    fake_llm.generate_reply.return_value = "gemini reply"
    monkeypatch.setattr(chat_service_module, "GeminiChatClient", MagicMock(return_value=fake_llm))

    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={
            "userid": 1,
            "data": {"window": 3, "agent": "test"},
            "message": "hello",
        },
    )
    assert response.status_code == 200
    assert response.json()["reply"] == "gemini reply"
