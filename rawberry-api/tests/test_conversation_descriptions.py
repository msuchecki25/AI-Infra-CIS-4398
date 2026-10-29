from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_chat_service
from app.conversation import describe_exchange
from app.main import create_app
from app.services.chat_service import ChatService
from app.store import InMemoryStore


@pytest.mark.parametrize('endpoint', ['/chat', '/chat/stream'])
def test_description_appears_after_first_success_and_stays_stable(endpoint):
    store = InMemoryStore()
    llm = MagicMock()
    llm.generate_reply.return_value = 'Solar panels convert sunlight into electricity.'
    app = create_app(store=store)
    app.dependency_overrides[get_chat_service] = lambda: ChatService(store, llm_client=llm)
    with TestClient(app, headers={'X-User-ID': 'alice'}) as client:
        created = client.post('/conversations', json={'title': 'Solar energy'}).json()
        assert created['description'] is None
        identifier = created['id']
        payload = {'conversation_id': identifier, 'message': 'How do solar panels work?'}
        assert client.post(endpoint, json=payload).status_code == 200
        saved = client.get('/conversations').json()[0]
        assert saved['title'] == 'Solar energy'
        assert saved['description'] == describe_exchange(payload['message'], llm.generate_reply.return_value)
        assert client.get('/conversations', headers={'X-User-ID': 'bob'}).json() == []
        llm.generate_reply.return_value = 'A different answer.'
        assert client.post(endpoint, json={'conversation_id': identifier, 'message': 'Another topic'}).status_code == 200
        assert client.get('/conversations').json()[0]['description'] == saved['description']
        assert llm.generate_reply.call_count == 2


def test_failed_turn_does_not_create_description():
    store = InMemoryStore()
    identifier = store.create_conversation('alice', 'Test')['id']
    turn = store.start_turn('alice', identifier, 'Failed question')
    store.finish_turn('alice', identifier, turn['id'], None)
    assert store.list_conversations('alice')[0]['description'] is None
    turn = store.start_turn('alice', identifier, 'Successful question')
    store.finish_turn('alice', identifier, turn['id'], 'Successful answer')
    assert store.list_conversations('alice')[0]['description'] == 'Question: Successful question Answer: Successful answer'


def test_description_is_bounded_and_normalizes_whitespace():
    assert describe_exchange(' A\n question\t here ', ' An\nanswer ') == 'Question: A question here Answer: An answer'
    description = describe_exchange('question ' * 5000, 'answer ' * 5000)
    assert len(description) <= 300 and '\n' not in description
    assert description.count('…') == 2
    assert len(describe_exchange('x' * 20000, 'y' * 20000)) <= 300
