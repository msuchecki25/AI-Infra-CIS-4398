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
from app.repository import ConversationBusy, ResourceNotFound, StorageError
from test_api import exercise_isolation


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
            connection.execute("INSERT INTO user_preference VALUES (42, 'legacy preference')")
            connection.execute("INSERT INTO ingested_item(public_id, user_id, content) VALUES (%s, 42, 'legacy item')", (str(uuid4()),))
            scoped_migration = (root / "migrations/002_user_scoping_conversations.sql").read_text()
            connection.execute(scoped_migration)
            connection.execute(scoped_migration)
        yield url
    finally:
        with psycopg.connect(base_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_data_survives_application_recreation_and_is_shared(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("USE_MOCK_CHAT", "true")
    with TestClient(create_app(), headers={'X-User-ID': 'alice'}) as first:
        uploaded = first.post("/upload", files=[
            ("files", ("notes.txt", b"alpha beta gamma", "text/plain")),
            ("files", ("paper.pdf", b"%PDF-1.7 example", "application/pdf")),
        ])
        assert uploaded.status_code == 200
        assert first.put("/me/system-prompt", json={"prompt": "Be concise"}).status_code == 200
        with TestClient(create_app(), headers={'X-User-ID': 'alice'}) as second:
            assert len(second.get("/documents").json()) == 2

    # New app/connection after both previous apps have shut down.
    with TestClient(create_app(), headers={'X-User-ID': 'alice'}) as restarted:
        documents = restarted.get("/documents").json()
        assert [d["chunk_count"] for d in documents] == [1, 0]
        assert restarted.get("/me/system-prompt").json()["prompt"] == "Be concise"
        assert restarted.get("/me/system-prompt", headers={"X-User-ID": "bob"}).json()["prompt"] == ""
        conversation_id = restarted.post('/conversations', json={'title': 'Persistent'}).json()['id']
        chat = restarted.post("/chat", json={"conversation_id": conversation_id, "message": "gamma?"})
        assert chat.status_code == 200
        assert "alpha beta gamma" in chat.json()["reply"]
        assert restarted.app.state.store.get_document_content("alice", documents[1]["id"]) == b"%PDF-1.7 example"
        assert restarted.put("/me/system-prompt", json={"prompt": ""}).status_code == 200
    with TestClient(create_app(), headers={'X-User-ID': 'alice'}) as final:
        assert final.get("/me/system-prompt").json()["prompt"] == ""
        history = final.get('/conversations/' + conversation_id + '/messages').json()
        assert [message['role'] for message in history] == ['user', 'assistant']
        assert final.get('/conversations/' + conversation_id + '/messages', headers={'X-User-ID': 'bob'}).status_code == 404


def test_failed_batch_rolls_back_documents_bytes_and_chunks(database_url):
    repository = PostgresRepository(database_url)
    first_id, second_id = str(uuid4()), str(uuid4())

    def document(identifier):
        return {"id": identifier, "owner_id": None, "filename": "notes.txt", "file_type": ".txt",
                "size_bytes": 5, "embedding_status": "pending", "metadata": {}}

    chunk = {"chunk_index": 0, "text": "alpha", "page_number": None, "status": "pending"}
    with pytest.raises(StorageError):
        repository.save_documents("alice", [
            (document(first_id), b"alpha", [chunk]),
            (document(second_id), b"alpha", [chunk, chunk]),  # duplicate index fails after earlier writes
        ])
    assert repository.list_documents("alice") == []
    assert repository.list_chunks("alice") == []
    for identifier in (first_id, second_id):
        with pytest.raises(ResourceNotFound):
            repository.get_document_content('alice', identifier)


def test_invalid_api_batch_writes_nothing(database_url):
    repository = PostgresRepository(database_url)
    with TestClient(create_app(store=repository), headers={'X-User-ID': 'alice'}) as client:
        response = client.post("/upload", files=[
            ("files", ("notes.txt", b"valid text", "text/plain")),
            ("files", ("invalid.pdf", b"invalid", "application/pdf")),
        ])
    assert response.status_code == 400
    assert repository.list_documents("alice") == []


def test_postgres_isolation_and_conversations(database_url):
    exercise_isolation(PostgresRepository(database_url))


def test_legacy_ownership_is_quarantined(database_url):
    import psycopg
    repository = PostgresRepository(database_url)
    assert repository.list_documents('42') == []
    assert repository.get_system_prompt('42') == ''
    with psycopg.connect(database_url) as connection:
        assert connection.execute('SELECT legacy_user_id, user_id FROM document WHERE id = 100').fetchone() == (42, None)
        assert connection.execute('SELECT count(*) FROM ingested_item').fetchone()[0] == 1  # Legacy text is retained, not exposed.
        assert connection.execute('SELECT system_prompt FROM legacy_user_preference WHERE user_id = 42').fetchone()[0] == 'legacy preference'


def test_postgres_serializes_conversation_turns_and_recovers_abandoned_work(database_url):
    import psycopg
    repository = PostgresRepository(database_url)
    other_instance = PostgresRepository(database_url)
    conversation = repository.create_conversation('alice', 'Concurrent')
    identifier = conversation['id']
    first = repository.start_turn('alice', identifier, 'first')
    with pytest.raises(ConversationBusy):
        other_instance.start_turn('alice', identifier, 'second')
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE chat_turn SET created_at = CURRENT_TIMESTAMP - INTERVAL '6 minutes' WHERE id = %s", (first['id'],))
    second = other_instance.start_turn('alice', identifier, 'recovered')
    with pytest.raises(ConversationBusy):
        repository.finish_turn('alice', identifier, first['id'], 'late')
    other_instance.finish_turn('alice', identifier, second['id'], 'success')
    assert [m['status'] for m in repository.list_messages('alice', identifier)] == ['failed', 'completed', 'completed']
