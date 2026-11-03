from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_chat_service
from app.main import create_app
from app.services.chat_service import ChatService
from app.store import InMemoryStore


@pytest.mark.parametrize("stream", [False, True])
def test_shared_corpora_and_private_conversations(monkeypatch, stream):
    monkeypatch.setenv("DEVELOPER_UPLOAD_API_KEY", "dev-secret")
    store = InMemoryStore()
    app = create_app(store=store)
    llm = MagicMock()
    llm.generate_reply.return_value = "answer"
    app.dependency_overrides[get_chat_service] = lambda: ChatService(store, llm_client=llm)
    with TestClient(app) as client:
        for path, text in [("/uploadmedical", b"gamma medical-source"),
                           ("/uploadedu", b"gamma education-source")]:
            files = [("files", ("source.txt", text, "text/plain"))]
            assert client.post(path, files=files).status_code == 403
            assert client.post(path, files=files, headers={"X-User-ID": "alice"}).status_code == 403
            assert client.post(path, files=files, headers={"X-Developer-Key": "bad"}).status_code == 403
            assert client.post(path, files=files, headers={"X-Developer-Key": "dev-secret"}).status_code == 200
            assert client.get(path).status_code == 422
            for user in ["alice", "bob"]:
                assert len(client.get(path, headers={"X-User-ID": user}).json()) == 1
        for domain in ["medical", "education"]:
            for user in ["alice", "bob"]:
                headers = {"X-User-ID": user}
                created = client.post("/conversations", headers=headers, json={"domain": domain})
                assert created.status_code == 201
                assert created.json()["domain"] == domain
                identifier = created.json()["id"]
                body = {"conversation_id": identifier, "message": "gamma"}
                path = "/chat/stream" if stream else "/chat"
                assert client.post(path, headers=headers, json=body).status_code == 200
                prompt = llm.generate_reply.call_args.args[0]
                assert domain + "-source" in prompt
                other = "education" if domain == "medical" else "medical"
                assert other + "-source" not in prompt
                assert client.post(path, headers={"X-User-ID": "other"}, json=body).status_code == 404
                assert client.post(path, headers=headers, json={**body, "domain": other}).status_code == 422
        assert client.post("/conversations", headers={"X-User-ID": "alice"}, json={"domain": "unknown"}).status_code == 422
        assert client.post("/conversations", headers={"X-User-ID": "corpus:medical"}, json={"domain": "medical"}).status_code == 422
        assert client.post("/upload").status_code == 404
        assert client.get("/documents").status_code == 404


def test_uploads_disabled_without_key(monkeypatch):
    monkeypatch.delenv("DEVELOPER_UPLOAD_API_KEY", raising=False)
    with TestClient(create_app(store=InMemoryStore())) as client:
        assert client.post("/uploadedu", files={"files": ("a.txt", b"hello")}).status_code == 503
