from uuid import uuid4

import psycopg
import pytest

from app.postgres_repository import PostgresRepository
from app.repository import ResourceNotFound
from test_postgres_integration import database_url  # noqa: F401


def expire(database_url, identifier):
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE chat_session SET updated_ts = CURRENT_TIMESTAMP - INTERVAL '25 hours' "
                           "WHERE public_id = %s", (identifier,))


def test_postgres_expiration_and_cleanup_of_related_rows(database_url):
    repository = PostgresRepository(database_url)
    expired = repository.create_conversation('alice', 'Expired')['id']
    active = repository.create_conversation('alice', 'Active')['id']
    turn = repository.start_turn('alice', expired, 'Question')
    repository.finish_turn('alice', expired, turn['id'], 'Answer')
    repository.set_system_prompt('alice', 'Be concise')
    document = {'id': str(uuid4()), 'filename': 'source.txt', 'file_type': '.txt', 'size_bytes': 5}
    repository.save_documents('alice', [(document, b'alpha', [{'chunk_index': 0, 'text': 'alpha'}])])
    # Include every FK dependent, even legacy rows attached to an API session.
    with psycopg.connect(database_url) as connection:
        internal = connection.execute('SELECT id FROM chat_session WHERE public_id = %s', (expired,)).fetchone()[0]
        connection.execute("INSERT INTO role VALUES (1, 'user')")
        connection.execute("INSERT INTO message VALUES (1, %s, 1, 'Legacy message', CURRENT_DATE)", (internal,))
        connection.execute("INSERT INTO citation VALUES (1, 1, 200, 0.5, CURRENT_DATE)")
        connection.execute("INSERT INTO chat_session_access VALUES (1, 42, %s, false)", (internal,))
    expire(database_url, expired)
    assert [row['id'] for row in repository.list_conversations('alice')] == [active]
    for operation in [lambda: repository.list_messages('alice', expired),
                      lambda: repository.start_turn('alice', expired, 'Cannot revive'),
                      lambda: repository.finish_turn('alice', expired, turn['id'], 'Late')]:
        with pytest.raises(ResourceNotFound):
            operation()
    assert repository.purge_expired_conversations() == 1
    assert repository.purge_expired_conversations() == 0
    with psycopg.connect(database_url) as connection:
        for table in ['chat_turn', 'message', 'citation', 'chat_session_access']:
            assert connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
        assert connection.execute('SELECT count(*) FROM document WHERE id = 100').fetchone()[0] == 1
    assert repository.get_document_content('alice', document['id']) == b'alpha'
    assert repository.get_system_prompt('alice') == 'Be concise'


def test_postgres_cleanup_skips_locked_sessions_and_recent_generations(database_url):
    repository = PostgresRepository(database_url)
    locked = repository.create_conversation('alice', 'Locked')['id']
    pending = repository.create_conversation('alice', 'Pending')['id']
    repository.start_turn('alice', pending, 'Generating')
    expire(database_url, locked)
    expire(database_url, pending)
    with psycopg.connect(database_url) as connection:
        connection.execute('SELECT id FROM chat_session WHERE public_id = %s FOR UPDATE', (locked,))
        assert repository.purge_expired_conversations() == 0
    assert repository.purge_expired_conversations(batch_size=1) == 1
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE chat_turn SET created_at = CURRENT_TIMESTAMP - INTERVAL '6 minutes'")
    assert repository.purge_expired_conversations() == 1


def test_postgres_activity_refreshes_retention(database_url):
    repository = PostgresRepository(database_url)
    identifier = repository.create_conversation('alice', 'Active')['id']
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE chat_session SET updated_ts = CURRENT_TIMESTAMP - INTERVAL '23 hours' "
                           "WHERE public_id = %s", (identifier,))
    turn = repository.start_turn('alice', identifier, 'New question')
    repository.finish_turn('alice', identifier, turn['id'], 'New answer')
    assert repository.purge_expired_conversations() == 0
    assert len(repository.list_messages('alice', identifier)) == 2
