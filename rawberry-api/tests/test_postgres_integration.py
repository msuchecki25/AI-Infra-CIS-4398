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
from app.retrieval.embeddings import HashEmbeddingProvider
from test_api import exercise_isolation


@pytest.fixture
def database_url(monkeypatch):
    base_url = os.getenv("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL/pgvector database")
    # Exercise real pgvector SQL without making paid Vertex AI requests.
    monkeypatch.setattr('app.postgres_repository.VertexEmbeddingProvider', lambda: HashEmbeddingProvider(768))
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
            vector_migration = (root / 'migrations/003_vector_embeddings.sql').read_text()
            connection.execute(vector_migration)
            connection.execute(vector_migration)
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
        assert [d['embedding_status'] for d in uploaded.json()] == ['completed', 'pending']
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


def test_ingestion_pipeline_indexes_documents_for_search(database_url):
    pytest.importorskip('langchain_text_splitters')
    import ingestion_pipeline

    path = Path(__file__).resolve().parents[2] / 'testdocs' / 'google.txt'
    raw_bytes = path.read_bytes()
    repository = PostgresRepository(database_url)
    document_id = ingestion_pipeline.ingest_document(
        repository, 'alice', str(path), raw_bytes, ingestion_pipeline.extract_pages('.txt', raw_bytes))

    documents = repository.list_documents('alice')
    assert [(d['id'], d['embedding_status']) for d in documents] == [(document_id, 'completed')]
    assert documents[0]['chunk_count'] == len(repository.list_chunks('alice')) > 1
    results = repository.search_chunks('alice', path.read_text().split('.')[0])
    assert results and results[0]['document_id'] == document_id
    assert repository.search_chunks('bob', 'google') == []


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


def test_pgvector_persists_ranks_and_filters_owners_and_models(database_url):
    import psycopg
    from app.retrieval.embeddings import EMBEDDING_MODEL

    class Vectors:
        def embed_document(self, text):
            return {'exact': [1.0, 0.0], 'related': [0.8, 0.6], 'unrelated': [0.0, 1.0]}[text] + [0.0] * 766

        def embed_query(self, text):
            return self.embed_document('exact')

    repository = PostgresRepository(database_url, embeddings=Vectors())
    def save(owner, text):
        document = {'id': str(uuid4()), 'filename': 'notes.txt', 'file_type': '.txt',
                    'size_bytes': len(text), 'metadata': {}}
        statuses = repository.save_documents(owner, [(document, text.encode(), [
            {'chunk_index': 0, 'text': text, 'page_number': 4, 'status': 'pending'},
        ])])
        assert statuses == ['completed']
        return document['id']

    related = save('alice', 'related')
    exact = save('alice', 'exact')
    save('alice', 'unrelated')
    save('bob', 'exact')
    # A recreated repository reads the stored vectors, not regenerated document vectors.
    restarted = PostgresRepository(database_url, embeddings=Vectors())
    results = restarted.search_chunks('alice', 'question', limit=5)
    assert [r['document_id'] for r in results] == [exact, related]
    assert [r['similarity'] for r in results] == pytest.approx([1.0, 0.8])
    assert results[0]['page_number'] == 4
    assert len(restarted.search_chunks('alice', 'question', limit=1)) == 1
    assert restarted.search_chunks('nobody', 'question') == []
    assert restarted.search_chunks('alice', '  ') == []
    assert restarted.search_chunks('alice', 'question', limit=0) == []

    with psycopg.connect(database_url) as connection:
        assert connection.execute('SELECT DISTINCT vector_dims(vector) FROM embedding').fetchall() == [(768,)]
        connection.execute('UPDATE embedding SET vector = %s::vector WHERE chunk_id = '
                           '(SELECT c.id FROM chunk c JOIN document d ON d.id = c.doc_id WHERE d.public_id::text = %s)',
                           ('[1,0]', exact))
        connection.execute('UPDATE embedding SET model = %s WHERE model = %s AND vector_dims(vector) = 768',
                           ('another-model', EMBEDDING_MODEL))
    assert restarted.search_chunks('alice', 'question') == []


def test_embedding_failure_writes_no_documents(database_url):
    class FailingEmbeddings:
        def embed_document(self, text):
            raise RuntimeError('private provider details')

    repository = PostgresRepository(database_url, embeddings=FailingEmbeddings())
    document = {'id': str(uuid4()), 'filename': 'notes.txt', 'file_type': '.txt', 'size_bytes': 5}
    with pytest.raises(StorageError, match='Embedding generation failed'):
        repository.save_documents('alice', [(document, b'alpha', [{'chunk_index': 0, 'text': 'alpha'}])])
    assert repository.list_documents('alice') == []


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
