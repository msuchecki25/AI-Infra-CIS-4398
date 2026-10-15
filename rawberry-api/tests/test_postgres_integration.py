"""Opt-in tests: TEST_DATABASE_URL must point to a disposable pgvector database.

Tests create/drop an isolated schema and enable the vector extension if needed.
They never read DATABASE_URL, preventing accidental use of an application database.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.postgres_repository import PostgresRepository
from app.repository import StorageError


@pytest.fixture
def database_url():
    base_url = os.getenv("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL/pgvector database")
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    root = Path(__file__).resolve().parents[2] / "rawberry-db"
    schema = "test_rawberry_" + uuid4().hex
    with psycopg.connect(base_url, autocommit=True) as admin:
        admin.execute((root / "init/01_extensions.sql").read_text())
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    url = make_conninfo(base_url, options=f"-c search_path={schema},public")
    try:
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute((root / "init/02_schema.sql").read_text())
            # Existing records must survive migration, with generated IDs avoiding collisions.
            connection.execute("INSERT INTO status VALUES (1, 'legacy')")
            connection.execute(
                "INSERT INTO document(id, user_id, status_id, created_at) VALUES (100, 42, 1, CURRENT_DATE)"
            )
            connection.execute(
                "INSERT INTO chunk(id, doc_id, chunk_index, content, created_at) "
                "VALUES (200, 100, 0, 'legacy content', CURRENT_DATE)"
            )
            migration = (root / "migrations/001_api_persistence.sql").read_text()
            connection.execute(migration)
            connection.execute(migration)
            assert connection.execute("SELECT content FROM chunk WHERE id = 200").fetchone()[0] == "legacy content"
        yield url
    finally:
        with psycopg.connect(base_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_data_survives_application_recreation_and_is_shared(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("USE_MOCK_CHAT", "true")
    with TestClient(create_app()) as first:
        ingested = first.post("/ingest", json={"userid": 42, "text": "saved text", "metadata": {"source": "test"}})
        assert ingested.status_code == 201
        uploaded = first.post("/upload", files=[
            ("files", ("notes.txt", b"alpha beta gamma", "text/plain")),
            ("files", ("paper.pdf", b"%PDF-1.7 example", "application/pdf")),
        ], data={"owner_id": "user-42"})
        assert uploaded.status_code == 200
        assert first.put("/users/42/system-prompt", json={"prompt": "Be concise"}).status_code == 200
        with TestClient(create_app()) as second:
            assert second.get("/get").json()["items"] == [ingested.json()["item"]]
            assert len(second.get("/documents").json()) == 2

    # New app/connection after both previous apps have shut down.
    with TestClient(create_app()) as restarted:
        documents = restarted.get("/documents").json()
        assert [d["chunk_count"] for d in documents] == [1, 0]
        assert restarted.get("/users/42/system-prompt").json()["prompt"] == "Be concise"
        assert restarted.get("/users/43/system-prompt").json()["prompt"] == ""
        chat = restarted.post("/chat", json={
            "userid": 42, "data": {"window": 1, "agent": "test"}, "message": "gamma?",
        })
        assert chat.status_code == 200
        assert "alpha beta gamma" in chat.json()["reply"]
        assert restarted.app.state.store.get_document_content(documents[1]["id"]) == b"%PDF-1.7 example"
        assert restarted.put("/users/42/system-prompt", json={"prompt": ""}).status_code == 200
    with TestClient(create_app()) as final:
        assert final.get("/users/42/system-prompt").json()["prompt"] == ""


def test_failed_batch_rolls_back_documents_bytes_and_chunks(database_url):
    repository = PostgresRepository(database_url)
    first_id, second_id = str(uuid4()), str(uuid4())

    def document(identifier):
        return {"id": identifier, "owner_id": None, "filename": "notes.txt", "file_type": ".txt",
                "size_bytes": 5, "embedding_status": "pending", "metadata": {}}

    chunk = {"chunk_index": 0, "text": "alpha", "page_number": None, "status": "pending"}
    with pytest.raises(StorageError):
        repository.save_documents([
            (document(first_id), b"alpha", [chunk]),
            (document(second_id), b"alpha", [chunk, chunk]),  # duplicate index fails after earlier writes
        ])
    assert repository.list_documents() == []
    assert repository.list_chunks() == []
    assert repository.get_document_content(first_id) is None
    assert repository.get_document_content(second_id) is None


def test_invalid_api_batch_writes_nothing(database_url):
    repository = PostgresRepository(database_url)
    with TestClient(create_app(store=repository)) as client:
        response = client.post("/upload", files=[
            ("files", ("notes.txt", b"valid text", "text/plain")),
            ("files", ("invalid.pdf", b"invalid", "application/pdf")),
        ])
    assert response.status_code == 400
    assert repository.list_documents() == []
