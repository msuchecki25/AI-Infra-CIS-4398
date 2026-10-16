"""PostgreSQL persistence behind the API storage boundary.

Connections are scoped to an operation; uploads use one transaction for the batch.
No DDL is run by the application. Apply the versioned migration before startup.
"""

from contextlib import contextmanager
from typing import Any

from app.repository import StorageError
from uuid import uuid4

from app.conversation import TURN_TIMEOUT_SECONDS, messages_from_turns
from app.repository import ConversationBusy, ResourceNotFound
from app.retrieval import rank_chunks


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
                ('002_user_scoping_conversations',),
            ).fetchone()
            if row is None:
                raise StorageError("Required database migration is missing")


    def save_documents(self, user_id: str, documents: list[tuple[dict[str, Any], bytes, list[dict[str, Any]]]]) -> None:
        from psycopg.types.json import Jsonb

        with self._connection() as connection:
            for document, content, chunks in documents:
                row = connection.execute(
                    "INSERT INTO document(public_id, user_id, filename, file_type, size_bytes, "
                    "embedding_status, metadata, status_id, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, "
                    "(SELECT id FROM status WHERE status = 'uploaded'), CURRENT_DATE) RETURNING id",
                    (document['id'], user_id, document['filename'], document['file_type'],
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

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return connection.execute(
                "SELECT d.public_id::text AS id, d.filename, d.file_type, d.size_bytes, d.user_id, "
                "d.embedding_status, d.metadata, (SELECT count(*) FROM chunk c WHERE c.doc_id = d.id) AS chunk_count "
                "FROM document d WHERE d.user_id = %s AND d.public_id IS NOT NULL ORDER BY d.uploaded_at, d.id", (user_id,)
            ).fetchall()

    def get_document_content(self, user_id: str, document_id: str) -> bytes:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT c.content FROM document_content c JOIN document d ON d.id = c.document_id "
                "WHERE d.user_id = %s AND d.public_id::text = %s", (user_id, document_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFound()
            return bytes(row['content'])

    def list_chunks(self, user_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return connection.execute(
                "SELECT d.public_id::text AS document_id, c.chunk_index, c.page_number, "
                "c.content AS text, c.processing_status AS status "
                "FROM chunk c JOIN document d ON d.id = c.doc_id "
                "WHERE d.user_id = %s AND d.public_id IS NOT NULL ORDER BY d.uploaded_at, d.id, c.chunk_index", (user_id,)
            ).fetchall()

    def search_chunks(self, user_id: str, query: str, limit: int = 3) -> list[dict[str, Any]]:
        return rank_chunks(self.list_chunks(user_id), query, limit)

    def get_system_prompt(self, user_id: str) -> str:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT system_prompt FROM user_preference WHERE user_id = %s", (user_id,),
            ).fetchone()
            return row['system_prompt'] if row else ''

    def set_system_prompt(self, user_id: str, prompt: str) -> None:
        with self._connection() as connection:
            if prompt:
                connection.execute(
                    "INSERT INTO user_preference(user_id, system_prompt) VALUES (%s, %s) "
                    "ON CONFLICT(user_id) DO UPDATE SET system_prompt = EXCLUDED.system_prompt", (user_id, prompt),
                )
            else:
                connection.execute("DELETE FROM user_preference WHERE user_id = %s", (user_id,))

    def create_conversation(self, user_id: str, title: str) -> dict[str, Any]:
        with self._connection() as connection:
            return connection.execute(
                "INSERT INTO chat_session(public_id, user_id, title, created_at) "
                "VALUES (%s, %s, %s, CURRENT_DATE) RETURNING public_id::text AS id, user_id, title, "
                "created_ts AS created_at, updated_ts AS updated_at", (str(uuid4()), user_id, title),
            ).fetchone()

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return connection.execute(
                "SELECT public_id::text AS id, user_id, title, created_ts AS created_at, updated_ts AS updated_at "
                "FROM chat_session WHERE user_id = %s AND public_id IS NOT NULL ORDER BY created_ts, id",
                (user_id,),
            ).fetchall()

    @staticmethod
    def _owned_conversation(connection, user_id: str, conversation_id: str):
        row = connection.execute(
            "SELECT id FROM chat_session WHERE user_id = %s AND public_id::text = %s FOR UPDATE",
            (user_id, conversation_id),
        ).fetchone()
        if row is None:
            raise ResourceNotFound()
        return row['id']

    def list_messages(self, user_id: str, conversation_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            session_id = self._owned_conversation(connection, user_id, conversation_id)
            turns = connection.execute(
                "SELECT id::text AS id, prompt, reply, status, created_at, completed_at "
                "FROM chat_turn WHERE session_id = %s ORDER BY ordinal", (session_id,),
            ).fetchall()
            return messages_from_turns(turns)

    def start_turn(self, user_id: str, conversation_id: str, message: str) -> dict[str, Any]:
        with self._connection() as connection:
            session_id = self._owned_conversation(connection, user_id, conversation_id)
            connection.execute(
                "UPDATE chat_turn SET status = 'failed', completed_at = CURRENT_TIMESTAMP "
                "WHERE session_id = %s AND status = 'pending' "
                "AND created_at <= CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')",
                (session_id, TURN_TIMEOUT_SECONDS),
            )
            if connection.execute(
                "SELECT 1 FROM chat_turn WHERE session_id = %s AND status = 'pending'", (session_id,),
            ).fetchone():
                raise ConversationBusy()
            ordinal = connection.execute(
                "UPDATE chat_session SET next_turn = next_turn + 1, updated_ts = CURRENT_TIMESTAMP "
                "WHERE id = %s RETURNING next_turn", (session_id,),
            ).fetchone()['next_turn']
            history = connection.execute(
                "SELECT prompt, reply FROM chat_turn WHERE session_id = %s AND status = 'completed' "
                "ORDER BY ordinal DESC LIMIT 10", (session_id,),
            ).fetchall()
            turn = connection.execute(
                "INSERT INTO chat_turn(id, session_id, ordinal, prompt, status) "
                "VALUES (%s, %s, %s, %s, 'pending') "
                "RETURNING id::text AS id, prompt, reply, status, created_at, completed_at",
                (str(uuid4()), session_id, ordinal, message),
            ).fetchone()
            return {**turn, 'history': list(reversed(history))}

    def finish_turn(self, user_id: str, conversation_id: str, turn_id: str, reply: str | None) -> None:
        with self._connection() as connection:
            session_id = self._owned_conversation(connection, user_id, conversation_id)
            result = connection.execute(
                "UPDATE chat_turn SET reply = %s, status = %s, completed_at = CURRENT_TIMESTAMP "
                "WHERE session_id = %s AND id::text = %s AND status = 'pending' RETURNING id",
                (reply, 'completed' if reply is not None else 'failed', session_id, turn_id),
            ).fetchone()
            if result is None:
                raise ConversationBusy()
            connection.execute("UPDATE chat_session SET updated_ts = CURRENT_TIMESTAMP WHERE id = %s", (session_id,))
