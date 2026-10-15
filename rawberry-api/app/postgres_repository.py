"""PostgreSQL persistence behind the API storage boundary.

Connections are scoped to an operation; uploads use one transaction for the batch.
No DDL is run by the application. Apply the versioned migration before startup.
"""

from contextlib import contextmanager
from typing import Any

from app.repository import StorageError
from app.store import InMemoryStore


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def _connection(self):
        import psycopg
        from psycopg.rows import dict_row

        try:
            with psycopg.connect(self._database_url, row_factory=dict_row, connect_timeout=5) as connection:
                yield connection
        except psycopg.Error as exc:
            raise StorageError("PostgreSQL operation failed") from exc

    def check_ready(self) -> None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT version FROM schema_migration WHERE version = %s",
                ('001_api_persistence',),
            ).fetchone()
            if row is None:
                raise StorageError("Required database migration is missing")

    def add(self, item: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb

        with self._connection() as connection:
            connection.execute(
                "INSERT INTO ingested_item(public_id, user_id, content, metadata) VALUES (%s, %s, %s, %s)",
                (item['id'], item.get('user_id'), item['text'], Jsonb(item.get('metadata', {}))),
            )

    def list_items(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return connection.execute(
                "SELECT public_id::text AS id, content AS text, metadata FROM ingested_item ORDER BY sequence_id"
            ).fetchall()

    def recent_items(self, count: int = 3) -> list[dict[str, Any]]:
        if count <= 0:
            return []
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT public_id::text AS id, content AS text, metadata FROM ingested_item "
                "ORDER BY sequence_id DESC LIMIT %s", (count,),
            ).fetchall()
            return list(reversed(rows))

    def save_documents(self, documents: list[tuple[dict[str, Any], bytes, list[dict[str, Any]]]]) -> None:
        from psycopg.types.json import Jsonb

        with self._connection() as connection:
            for document, content, chunks in documents:
                row = connection.execute(
                    "INSERT INTO document(public_id, owner_id, filename, file_type, size_bytes, "
                    "embedding_status, metadata, status_id, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, "
                    "(SELECT id FROM status WHERE status = 'uploaded'), CURRENT_DATE) RETURNING id",
                    (document['id'], document.get('owner_id'), document['filename'], document['file_type'],
                     document['size_bytes'], document['embedding_status'], Jsonb(document.get('metadata', {}))),
                ).fetchone()
                internal_id = row['id']
                connection.execute(
                    "INSERT INTO document_content(document_id, content) VALUES (%s, %s)",
                    (internal_id, content),
                )
                for chunk in chunks:
                    connection.execute(
                        "INSERT INTO chunk(doc_id, chunk_index, content, page_number, processing_status, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)",
                        (internal_id, chunk['chunk_index'], chunk['text'], chunk.get('page_number'), chunk['status']),
                    )

    def list_documents(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return connection.execute(
                "SELECT d.public_id::text AS id, d.filename, d.file_type, d.size_bytes, d.owner_id, "
                "d.embedding_status, d.metadata, (SELECT count(*) FROM chunk c WHERE c.doc_id = d.id) AS chunk_count "
                "FROM document d WHERE d.public_id IS NOT NULL ORDER BY d.uploaded_at, d.id"
            ).fetchall()

    def get_document_content(self, document_id: str) -> bytes | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT c.content FROM document_content c JOIN document d ON d.id = c.document_id "
                "WHERE d.public_id::text = %s", (document_id,),
            ).fetchone()
            return bytes(row['content']) if row else None

    def list_chunks(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return connection.execute(
                "SELECT d.public_id::text AS document_id, d.owner_id, c.chunk_index, c.page_number, "
                "c.content AS text, c.processing_status AS status "
                "FROM chunk c JOIN document d ON d.id = c.doc_id "
                "WHERE d.public_id IS NOT NULL ORDER BY d.uploaded_at, d.id, c.chunk_index"
            ).fetchall()

    def search_chunks(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        # Preserve the prototype's keyword ranking. Semantic retrieval belongs to
        # the subsequent embedding/RAG integration; no vectors are fabricated here.
        if not query or limit <= 0:
            return []
        store = InMemoryStore()
        for chunk in self.list_chunks():
            store.add_chunk(chunk)
        return store.search_chunks(query, limit)

    def get_system_prompt(self, userid: int) -> str:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT system_prompt FROM user_preference WHERE user_id = %s", (userid,),
            ).fetchone()
            return row['system_prompt'] if row else ''

    def set_system_prompt(self, userid: int, prompt: str) -> None:
        with self._connection() as connection:
            if prompt:
                connection.execute(
                    "INSERT INTO user_preference(user_id, system_prompt) VALUES (%s, %s) "
                    "ON CONFLICT(user_id) DO UPDATE SET system_prompt = EXCLUDED.system_prompt", (userid, prompt),
                )
            else:
                connection.execute("DELETE FROM user_preference WHERE user_id = %s", (userid,))
