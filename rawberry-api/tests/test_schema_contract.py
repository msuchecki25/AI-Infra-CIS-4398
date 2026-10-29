"""Validate real migrated PostgreSQL rows against the public API contracts.

Uses the isolated, disposable database fixture; never the application's database.
"""
from uuid import UUID, uuid4

from app.models import ConversationRecord, DocumentChunk, DocumentRecord, MessageRecord
from app.postgres_repository import PostgresRepository
from test_postgres_integration import database_url  # noqa: F401


def test_migrated_database_round_trips_public_models(database_url):
    repository = PostgresRepository(database_url)
    repository.check_ready()
    owner = 'Alice-042'
    identifier = str(uuid4())
    document = DocumentRecord(
        id=identifier, user_id=owner, filename='contract.txt', file_type='.txt',
        size_bytes=5, metadata={'source': 'contract-test', 'nested': {'page': 7}},
    )
    chunk = DocumentChunk(document_id=identifier, chunk_index=0, page_number=7, text='alpha')
    assert repository.save_documents(owner, [(document.model_dump(), b'alpha', [chunk.model_dump()])]) == ['completed']

    # Strict validation catches SQL type drift instead of letting Pydantic coerce it.
    saved = DocumentRecord.model_validate(repository.list_documents(owner)[0], strict=True)
    assert saved.id == identifier and UUID(saved.id)
    assert saved.user_id == owner
    assert saved.metadata == document.metadata
    assert saved.filename == document.filename and saved.file_type == document.file_type
    assert saved.size_bytes == 5 and saved.chunk_count == 1
    assert saved.embedding_status == 'completed'
    assert repository.get_document_content(owner, saved.id) == b'alpha'
    saved_chunk = DocumentChunk.model_validate(repository.list_chunks(owner)[0], strict=True)
    assert saved_chunk == chunk.model_copy(update={'status': 'completed'})

    repository.set_system_prompt(owner, 'Keep answers short.')
    assert repository.get_system_prompt(owner) == 'Keep answers short.'
    repository.set_system_prompt(owner, '')
    assert repository.get_system_prompt(owner) == ''

    conversation = ConversationRecord.model_validate(repository.create_conversation(owner, 'Contract'), strict=True)
    assert UUID(conversation.id) and conversation.user_id == owner
    assert conversation.title == 'Contract'
    assert conversation.created_at.utcoffset() is not None
    assert conversation.updated_at.utcoffset() is not None
    assert ConversationRecord.model_validate(repository.list_conversations(owner)[0], strict=True) == conversation

    turn = repository.start_turn(owner, conversation.id, 'Question')
    pending = MessageRecord.model_validate(repository.list_messages(owner, conversation.id)[0], strict=True)
    assert (pending.turn_id, pending.role, pending.content, pending.status) == (turn['id'], 'user', 'Question', 'pending')
    repository.finish_turn(owner, conversation.id, turn['id'], 'Answer')
    failed_turn = repository.start_turn(owner, conversation.id, 'Another question')
    repository.finish_turn(owner, conversation.id, failed_turn['id'], None)
    messages = [MessageRecord.model_validate(row, strict=True)
                for row in repository.list_messages(owner, conversation.id)]
    assert [(message.role, message.content, message.status) for message in messages] == [
        ('user', 'Question', 'completed'), ('assistant', 'Answer', 'completed'),
        ('user', 'Another question', 'failed'),
    ]
    assert len({message.id for message in messages}) == 3
    assert all(message.created_at.utcoffset() is not None for message in messages)
    assert messages[0].turn_id == messages[1].turn_id == turn['id']
    assert messages[2].turn_id == failed_turn['id']
