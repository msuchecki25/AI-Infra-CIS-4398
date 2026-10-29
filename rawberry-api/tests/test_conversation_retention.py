from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_chat_service
from app.main import create_app
from app.repository import ResourceNotFound
from app.services.chat_service import ChatService
from app.store import InMemoryStore


@pytest.mark.parametrize('age,expired', [
    (timedelta(hours=24) - timedelta(microseconds=1), False),
    (timedelta(hours=24), True),
    (timedelta(hours=25), True),
])
def test_expiration_boundary_and_api_enforcement(monkeypatch, age, expired):
    store = InMemoryStore()
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(store, '_now', lambda: started)
    identifier = store.create_conversation('alice', 'Retention')['id']
    turn = store.start_turn('alice', identifier, 'Original question')
    store.finish_turn('alice', identifier, turn['id'], 'Original answer')
    monkeypatch.setattr(store, '_now', lambda: started + age)
    llm = MagicMock()
    llm.generate_reply.return_value = 'New answer'
    app = create_app(store=store)
    app.dependency_overrides[get_chat_service] = lambda: ChatService(store, llm_client=llm)
    with TestClient(app, headers={'X-User-ID': 'alice'}) as client:
        listing = client.get('/conversations').json()
        assert len(listing) == (0 if expired else 1)
        assert client.get(f'/conversations/{identifier}/messages').status_code == (404 if expired else 200)
        # Reading never extends retention.
        assert store._conversations[identifier]['updated_at'] == started
        for endpoint in ['/chat', '/chat/stream']:
            response = client.post(endpoint, json={'conversation_id': identifier, 'message': 'Follow up'})
            assert response.status_code == (404 if expired else 200)
        assert client.get(f'/conversations/{identifier}/messages', headers={'X-User-ID': 'bob'}).status_code == 404
    if expired:
        llm.generate_reply.assert_not_called()
        assert len(store._turns[identifier]) == 1  # expired chats cannot be revived


def test_activity_extends_ttl_and_cleanup_preserves_other_data(monkeypatch):
    store = InMemoryStore()
    clock = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    monkeypatch.setattr(store, '_now', lambda: clock[0])
    old = store.create_conversation('alice', 'Old')['id']
    active = store.create_conversation('alice', 'Active')['id']
    other = store.create_conversation('bob', 'Old too')['id']
    store.set_system_prompt('alice', 'Be concise')
    store.save_documents('alice', [({'id': 'document', 'embedding_status': 'pending'}, b'alpha', [])])
    clock[0] += timedelta(hours=23)
    turn = store.start_turn('alice', active, 'Question')
    clock[0] += timedelta(minutes=1)
    store.finish_turn('alice', active, turn['id'], 'Answer')
    clock[0] += timedelta(hours=1)
    assert [c['id'] for c in store.list_conversations('alice')] == [active]
    assert store.purge_expired_conversations(batch_size=1) == 1
    assert store.purge_expired_conversations() == 1
    assert store.purge_expired_conversations() == 0
    assert old not in store._turns and other not in store._turns
    assert len(store.list_messages('alice', active)) == 2
    assert store.get_document_content('alice', 'document') == b'alpha'
    assert store.get_system_prompt('alice') == 'Be concise'
    # Finishing the turn also extends the window.
    clock[0] = datetime(2026, 1, 2, 23, tzinfo=timezone.utc)
    assert store.list_conversations('alice')
    clock[0] += timedelta(minutes=1)
    with pytest.raises(ResourceNotFound):
        store.list_messages('alice', active)


def test_cleanup_protects_recent_pending_turn_but_not_abandoned_turn(monkeypatch):
    store = InMemoryStore()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(store, '_now', lambda: now)
    identifier = store.create_conversation('alice', 'Pending')['id']
    store.start_turn('alice', identifier, 'Question')
    store._conversations[identifier]['updated_at'] = now - timedelta(days=1)
    assert store.purge_expired_conversations() == 0
    monkeypatch.setattr(store, '_now', lambda: now + timedelta(minutes=5))
    assert store.purge_expired_conversations() == 1


def test_cleanup_command_requires_database_and_valid_batch(monkeypatch):
    from app.cleanup_conversations import main
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr('sys.argv', ['cleanup'])
    with pytest.raises(SystemExit, match='2'):
        main()
    monkeypatch.setattr('sys.argv', ['cleanup', '--batch-size', '0'])
    with pytest.raises(SystemExit, match='2'):
        main()
