from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.postgres_repository import PostgresRepository
from app.repository import StorageError
from app.store import InMemoryStore


def test_database_selection_and_explicit_test_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/rawberry")
    assert Settings.from_env().database_url == "postgresql://localhost/rawberry"
    assert isinstance(create_app().state.store, PostgresRepository)
    memory = InMemoryStore()
    assert create_app(store=memory).state.store is memory
    monkeypatch.setenv("DATABASE_URL", "  ")
    assert isinstance(create_app().state.store, InMemoryStore)


def test_configured_database_failure_does_not_fall_back_to_memory(monkeypatch):
    import psycopg

    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/rawberry")
    app = create_app()
    with patch("psycopg.connect", side_effect=psycopg.OperationalError("private connection details")):
        with pytest.raises(StorageError):
            with TestClient(app):
                pass
    assert isinstance(app.state.store, PostgresRepository)


def test_database_errors_have_safe_api_response():
    class UnavailableStore(InMemoryStore):
        def list_documents(self, user_id):
            raise StorageError("private connection details")

    with TestClient(create_app(store=UnavailableStore()), headers={'X-User-ID': 'alice'}) as client:
        response = client.get("/uploadedu")
    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "error_code": "STORAGE_UNAVAILABLE",
        "message": "Storage is temporarily unavailable.",
    }


def test_document_listing_and_txt_source_locations():
    store = InMemoryStore()
    with TestClient(create_app(store=store), headers={'X-User-ID': 'alice'}) as client:
        upload = client.post("/uploadedu", headers={'X-Developer-Key': 'test-upload-key'}, files=[("files", ("notes.txt", b"alpha " * 400, "text/plain"))])
        assert upload.status_code == 200
        documents = client.get("/uploadedu").json()
    assert len(documents) == 1
    assert documents[0]["id"] == upload.json()[0]["document_id"]
    assert documents[0]["chunk_count"] == len(store.list_chunks('corpus:education'))
    assert all(chunk["page_number"] is None for chunk in store.list_chunks('corpus:education'))


def test_upload_schema_marks_array_items_as_binary_files():
    schema = create_app(store=InMemoryStore()).openapi()
    body = schema["paths"]["/uploadedu"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]
    model = schema["components"]["schemas"][body["$ref"].split("/")[-1]]
    files = model["properties"]["files"]
    assert files["type"] == "array"
    assert files["items"]["format"] == "binary"


@pytest.mark.parametrize('missing_version', [None, '005_conversation_descriptions', '006_chat_domains'])
def test_readiness_requires_description_and_domain_migrations(missing_version):
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    connection = MagicMock()

    def execute(query, parameters):
        version, = parameters
        result = MagicMock()
        result.fetchone.return_value = None if version == missing_version else {'version': version}
        return result

    connection.execute.side_effect = execute

    @contextmanager
    def connect():
        yield connection

    repository = PostgresRepository('unused')
    repository._connection = connect
    if missing_version:
        with pytest.raises(StorageError, match='Required database migration is missing'):
            repository.check_ready()
    else:
        repository.check_ready()
        assert connection.execute.call_count == 2
