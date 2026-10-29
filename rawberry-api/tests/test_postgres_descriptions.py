import psycopg
import pytest

from app.postgres_repository import PostgresRepository
from app.repository import ResourceNotFound, StorageError
from app.user_models import ConversationRecord
from test_postgres_integration import database_url  # noqa: F401


def test_description_persists_and_is_only_set_by_successful_owned_turn(database_url):
    repository = PostgresRepository(database_url)
    created = repository.create_conversation('alice', 'Persistent description')
    assert created['description'] is None
    identifier = created['id']
    failed = repository.start_turn('alice', identifier, 'Failed question')
    repository.finish_turn('alice', identifier, failed['id'], None)
    assert repository.list_conversations('alice')[0]['description'] is None
    turn = repository.start_turn('alice', identifier, 'First question')
    with pytest.raises(ResourceNotFound):
        repository.finish_turn('bob', identifier, turn['id'], 'Not the owner')
    repository.finish_turn('alice', identifier, turn['id'], 'First answer')
    restarted = PostgresRepository(database_url)
    saved = ConversationRecord.model_validate(restarted.list_conversations('alice')[0], strict=True)
    assert saved.description == 'Question: First question Answer: First answer'
    assert restarted.list_conversations('bob') == []
    later = restarted.start_turn('alice', identifier, 'Second question')
    restarted.finish_turn('alice', identifier, later['id'], 'Second answer')
    assert restarted.list_conversations('alice')[0]['description'] == saved.description
    with psycopg.connect(database_url) as connection:
        connection.execute('UPDATE chat_session SET description = NULL WHERE public_id = %s', (identifier,))
    later = restarted.start_turn('alice', identifier, 'Backfill question')
    restarted.finish_turn('alice', identifier, later['id'], 'Backfill answer')
    assert restarted.list_conversations('alice')[0]['description'] == 'Question: Backfill question Answer: Backfill answer'


def test_description_database_length_constraint_and_readiness(database_url):
    repository = PostgresRepository(database_url)
    identifier = repository.create_conversation('alice', 'Bounded')['id']
    turn = repository.start_turn('alice', identifier, 'word ' * 4000)
    repository.finish_turn('alice', identifier, turn['id'], 'answer ' * 4000)
    assert len(repository.list_conversations('alice')[0]['description']) <= 300
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(database_url) as connection:
            connection.execute('UPDATE chat_session SET description = %s WHERE public_id = %s', ('x' * 301, identifier))
    with psycopg.connect(database_url) as connection:
        connection.execute("DELETE FROM schema_migration WHERE version = '005_conversation_descriptions'")
    with pytest.raises(StorageError, match='Required database migration is missing'):
        repository.check_ready()
