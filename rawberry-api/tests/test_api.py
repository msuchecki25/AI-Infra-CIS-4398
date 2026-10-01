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


def test_chat_stream_emits_lifecycle_status_and_final_response(monkeypatch):
    monkeypatch.setenv("USE_MOCK_CHAT", "true")
    app = create_app()
    client = TestClient(app)

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "userid": 1,
            "data": {"window": 3, "agent": "test"},
            "message": "hello",
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert body.index('"status":"received"') < body.index('"status":"generating"')
    assert body.index('"status":"generating"') < body.index('"status":"completed"')
    assert '"reply":"You said: hello"' in body


def test_chat_stream_emits_failure_status_without_exposing_exception():
    from app.api.routes import get_chat_service

    class FailingChatService:
        def generate_reply(self, request):
            raise RuntimeError("private provider detail")

    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: FailingChatService()
    client = TestClient(app)

    response = client.post(
        "/chat/stream",
        json={
            "userid": 1,
            "data": {"window": 3, "agent": "test"},
            "message": "hello",
        },
    )

    assert response.status_code == 200
    assert '"status":"failed"' in response.text
    assert "The response could not be generated." in response.text
    assert "private provider detail" not in response.text


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


def test_upload_endpoint_accepts_text_file_and_returns_chunk_summary():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/upload",
        files=[("files", ("sample.txt", b"alpha beta gamma delta", "text/plain"))],
        data={"owner_id": "user-123"},
    )

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["success"] is True
    assert payload["status"] == "uploaded"
    assert payload["filename"] == "sample.txt"
    assert payload["chunk_count"] >= 1
    assert payload["document_id"]


def test_upload_endpoint_rejects_unsupported_file_type():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/upload",
        files=[("files", ("sample.csv", b"a,b,c", "text/csv"))],
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_FILE_TYPE"


def test_upload_endpoint_processes_all_files_and_keeps_binary_contents():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/upload",
        files=[
            ("files", ("sample.txt", b"hello", "text/plain")),
            ("files", ("sample.pdf", b"%PDF-1.7 binary payload", "application/pdf")),
        ],
    )

    assert response.status_code == 200
    uploads = response.json()
    assert [upload["filename"] for upload in uploads] == ["sample.txt", "sample.pdf"]
    assert uploads[1]["chunk_count"] == 0
    assert app.state.store.get_document_content(uploads[1]["document_id"]) == b"%PDF-1.7 binary payload"


def test_upload_endpoint_rejects_invalid_batch_without_storing_partial_results():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/upload",
        files=[
            ("files", ("valid.txt", b"hello", "text/plain")),
            ("files", ("invalid.pdf", b"not a PDF", "application/pdf")),
        ],
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_FILE_CONTENT"
    assert app.state.store.list_documents() == []


def test_upload_endpoint_rejects_oversized_file_before_reading_it_all(monkeypatch):
    from app.services.ingest_service import IngestService

    monkeypatch.setattr(IngestService, "MAX_FILE_SIZE_BYTES", 4)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/upload",
        files=[("files", ("large.txt", b"12345", "text/plain"))],
    )

    assert response.status_code == 413
    assert response.json()["error_code"] == "FILE_TOO_LARGE"
    assert app.state.store.list_documents() == []


def test_upload_endpoint_rejects_non_utf8_text():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/upload",
        files=[("files", ("invalid.txt", b"\xff\xfe", "text/plain"))],
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_TEXT_ENCODING"


def test_chat_uses_retrieved_document_chunks_as_context():
    app = create_app()
    client = TestClient(app)

    upload = client.post(
        "/upload",
        files=[("files", ("sample.txt", b"alpha beta gamma delta", "text/plain"))],
        data={"owner_id": "user-123"},
    )
    assert upload.status_code == 200

    response = client.post(
        "/chat",
        json={
            "userid": 1,
            "data": {"window": 3, "agent": "test"},
            "message": "What is gamma?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "gamma" in payload["reply"].lower()
    assert "alpha beta gamma delta" in payload["reply"].lower()
