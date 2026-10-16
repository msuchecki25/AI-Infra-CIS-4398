import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_chat_service
from app.config import Settings
from app.main import create_app
from app.repository import ConversationBusy, ResourceNotFound
from app.services.chat_service import ChatService
from app.store import InMemoryStore


@pytest.fixture
def client():
    with TestClient(create_app(store=InMemoryStore()), headers={'X-User-ID': 'alice'}) as client:
        yield client


def conversation(client, user='alice'):
    response = client.post('/conversations', headers={'X-User-ID': user}, json={'title': 'Research'})
    assert response.status_code == 201
    return response.json()['id']


def ask(client, identifier, message='hello', user='alice', stream=False):
    return client.post('/chat/stream' if stream else '/chat', headers={'X-User-ID': user},
                       json={'conversation_id': identifier, 'message': message})


def upload(client, text=b'alpha gamma alice secret', user='alice', name='notes.txt'):
    return client.post('/upload', headers={'X-User-ID': user}, files=[('files', (name, text, 'text/plain'))])


def test_public_endpoints_and_isolated_storage():
    a, b = create_app(store=InMemoryStore()), create_app(store=InMemoryStore())
    a.state.store.add('alice', {'id': 'one', 'text': 'alpha', 'metadata': {}})
    assert len(a.state.store.list_items('alice')) == 1
    assert b.state.store.list_items('alice') == []
    with TestClient(a) as client:
        assert client.get('/health').json() == {'status': 'healthy'}
        root = client.get('/').json()
        assert root['message'] == 'RAWBerry API is running'
        assert '/conversations' in root['available_endpoints']


@pytest.mark.parametrize('method,path,body', [
    ('get', '/get', None), ('get', '/documents', None), ('get', '/conversations', None),
    ('get', '/me/system-prompt', None), ('put', '/me/system-prompt', {'prompt': 'hi'}),
    ('post', '/ingest', {'text': 'hello'}), ('post', '/conversations', {}),
    ('post', '/chat', {'conversation_id': str(uuid4()), 'message': 'hi'}),
    ('post', '/chat/stream', {'conversation_id': str(uuid4()), 'message': 'hi'}),
    ('get', '/conversations/' + str(uuid4()) + '/messages', None),
])
def test_every_data_route_requires_user_context(method, path, body):
    with TestClient(create_app(store=InMemoryStore())) as client:
        assert client.request(method, path, json=body).status_code == 422


def test_upload_requires_user_context():
    with TestClient(create_app(store=InMemoryStore())) as client:
        assert client.post('/upload', files=[('files', ('a.txt', b'hello', 'text/plain'))]).status_code == 422


@pytest.mark.parametrize('identifier', ['', ' ', ' alice', 'alice ', 'a b', 'a' * 129])
def test_invalid_user_context_rejected(client, identifier):
    assert client.get('/get', headers={'X-User-ID': identifier}).status_code == 422


def test_duplicate_identity_rejected():
    with TestClient(create_app(store=InMemoryStore())) as client:
        assert client.get('/get', headers=[('X-User-ID', 'alice'), ('X-User-ID', 'bob')]).status_code == 422


def test_identity_is_case_sensitive_and_not_numeric(client):
    for user in ['42', '042', 'Alice', 'alice']:
        assert client.post('/ingest', headers={'X-User-ID': user}, json={'text': user}).status_code == 201
    for user in ['42', '042', 'Alice', 'alice']:
        assert [i['text'] for i in client.get('/get', headers={'X-User-ID': user}).json()['items']] == [user]


def test_removed_identity_fields_and_old_contract_rejected(client):
    assert client.post('/ingest', json={'text': 'hello', 'userid': 'bob'}).status_code == 422
    assert client.post('/chat', json={'userid': 42, 'data': {'window': 1, 'agent': 'test'}, 'message': 'hello'}).status_code == 422
    assert client.post('/upload', files=[('files', ('a.txt', b'hello', 'text/plain'))], data={'owner_id': 'bob'}).status_code == 422
    assert client.put('/me/system-prompt', json={'prompt': 'hello', 'user_id': 'bob'}).status_code == 422
    assert client.get('/users/bob/system-prompt').status_code == 404
    assert client.get('/get?user_id=bob').status_code == 422


def exercise_isolation(store):
    app = create_app(store=store)
    captured = []
    class CapturingLLM:
        def generate_reply(self, message):
            captured.append(message)
            return 'answer-' + str(len(captured))
    app.dependency_overrides[get_chat_service] = lambda: ChatService(store, llm_client=CapturingLLM())
    with TestClient(app, headers={'X-User-ID': 'alice'}) as client:
        for user in ['alice', 'bob']:
            assert client.post('/ingest', headers={'X-User-ID': user}, json={'text': user + '-item'}).json()['count'] == 1
            assert client.put('/me/system-prompt', headers={'X-User-ID': user}, json={'prompt': user + '-preference'}).status_code == 200
            assert upload(client, text=('gamma ' + user + '-document').encode(), user=user).status_code == 200
        first, second, other = conversation(client), conversation(client), conversation(client, 'bob')
        assert len(client.get('/conversations').json()) == 2
        assert len(client.get('/documents').json()) == 1
        assert client.get('/get').json()['items'][0]['text'] == 'alice-item'
        assert client.get('/me/system-prompt').json() == {'user_id': 'alice', 'prompt': 'alice-preference'}
        assert client.get('/conversations/' + other + '/messages').status_code == 404
        assert ask(client, other).status_code == 404
        assert ask(client, other, stream=True).status_code == 404
        assert ask(client, str(uuid4())).status_code == 404
        first_reply = ask(client, first, 'gamma first-conversation-only')
        assert first_reply.status_code == 200
        assert first_reply.json()['recent_items'][0]['text'] == 'alice-item'
        assert 'alice-document' in captured[-1] and 'bob-document' not in captured[-1]
        assert 'alice-preference' in captured[-1] and 'bob-preference' not in captured[-1]
        assert ask(client, first, 'follow-up').status_code == 200
        assert 'first-conversation-only' in captured[-1] and 'answer-1' in captured[-1]
        assert ask(client, second, 'gamma separate').status_code == 200
        assert 'first-conversation-only' not in captured[-1]
        assert 'alice-document' in captured[-1]  # all of this user's documents are available in every chat
        assert ask(client, other, 'gamma', user='bob').status_code == 200
        assert 'bob-document' in captured[-1] and 'alice-document' not in captured[-1]
        history = client.get('/conversations/' + first + '/messages').json()
        assert [m['role'] for m in history] == ['user', 'assistant', 'user', 'assistant']
        assert [m['content'] for m in history] == ['gamma first-conversation-only', 'answer-1', 'follow-up', 'answer-2']
        assert all(m['status'] == 'completed' for m in history)
        alice_document = store.list_documents('alice')[0]['id']
        with pytest.raises(ResourceNotFound):
            store.get_document_content('bob', alice_document)


def test_users_and_conversations_are_isolated():
    exercise_isolation(InMemoryStore())


def test_stream_events_and_persisted_history(client):
    identifier = conversation(client)
    response = ask(client, identifier, stream=True)
    assert response.status_code == 200
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    assert [e['status'] for e in events] == ['received', 'generating', 'completed']
    assert len({e['request_id'] for e in events}) == 1
    assert events[-1]['response']['reply'] == 'You said: hello'
    assert len(client.get('/conversations/' + identifier + '/messages').json()) == 2


@pytest.mark.parametrize('stream', [False, True])
def test_generation_failure_is_recorded_and_can_be_retried(stream):
    store = InMemoryStore()
    app = create_app(store=store)
    llm = MagicMock()
    llm.generate_reply.side_effect = RuntimeError('private provider details')
    app.dependency_overrides[get_chat_service] = lambda: ChatService(store, llm_client=llm)
    with TestClient(app, headers={'X-User-ID': 'alice'}) as client:
        identifier = conversation(client)
        response = ask(client, identifier, stream=stream)
        assert response.status_code == (200 if stream else 502)
        assert 'private provider details' not in response.text
        if stream:
            assert '"status":"failed"' in response.text
            assert '"status":"completed"' not in response.text
        messages = client.get('/conversations/' + identifier + '/messages').json()
        assert len(messages) == 1 and messages[0]['status'] == 'failed'
        llm.generate_reply.side_effect = None
        llm.generate_reply.return_value = 'recovered'
        assert ask(client, identifier).status_code == 200
        messages = client.get('/conversations/' + identifier + '/messages').json()
        assert [m['status'] for m in messages] == ['failed', 'completed', 'completed']


def test_concurrent_turns_and_abandoned_turn_recovery(client):
    store = client.app.state.store
    identifier = conversation(client)
    old = store.start_turn('alice', identifier, 'first')
    assert ask(client, identifier).status_code == 409
    assert ask(client, identifier, stream=True).status_code == 409
    store._turns[identifier][0]['created_at'] = datetime.now(timezone.utc) - timedelta(minutes=6)
    assert ask(client, identifier).status_code == 200
    with pytest.raises(ConversationBusy):
        store.finish_turn('alice', identifier, old['id'], 'late response')
    assert store.list_messages('alice', identifier)[0]['status'] == 'failed'


def test_preferences_update_clear_and_validation(client):
    assert client.get('/me/system-prompt').json()['prompt'] == ''
    assert client.put('/me/system-prompt', json={'prompt': 'Concise'}).status_code == 200
    assert client.get('/me/system-prompt', headers={'X-User-ID': 'bob'}).json()['prompt'] == ''
    assert client.put('/me/system-prompt', json={'prompt': ''}).status_code == 200
    assert client.get('/me/system-prompt').json()['prompt'] == ''
    assert client.put('/me/system-prompt', json={'prompt': 'x' * 2001}).status_code == 422
    assert client.post('/chat', json={'conversation_id': conversation(client), 'message': ''}).status_code == 422


def test_upload_retains_bytes_and_txt_chunks(client):
    response = upload(client, b'hello gamma')
    assert response.status_code == 200
    document = response.json()[0]
    assert document['chunk_count'] == 1 and document['embedding_status'] == 'pending'
    store = client.app.state.store
    assert store.get_document_content('alice', document['document_id']) == b'hello gamma'
    assert store.list_chunks('alice')[0]['page_number'] is None
    assert store.list_chunks('bob') == []
    assert upload(client, b'%PDF-1.7 sample', name='paper.pdf').json()[0]['chunk_count'] == 0


@pytest.mark.parametrize('name,content,status,code', [
    ('a.csv', b'a,b', 400, 'INVALID_FILE_TYPE'),
    ('a.txt', b'', 400, 'EMPTY_FILE'),
    ('a.txt', b'\xff\xfe', 400, 'INVALID_TEXT_ENCODING'),
    ('a.pdf', b'not pdf', 400, 'INVALID_FILE_CONTENT'),
    ('a.docx', b'not zip', 400, 'INVALID_FILE_CONTENT'),
])
def test_invalid_uploads(client, name, content, status, code):
    response = upload(client, content, name=name)
    assert response.status_code == status
    assert response.json()['error_code'] == code
    assert client.app.state.store.list_documents('alice') == []


def test_upload_batch_validation_and_size_limit(client, monkeypatch):
    response = client.post('/upload', files=[('files', ('a.txt', b'hello', 'text/plain')),
                                            ('files', ('b.pdf', b'invalid', 'application/pdf'))])
    assert response.status_code == 400
    assert client.app.state.store.list_documents('alice') == []
    from app.services.ingest_service import IngestService
    monkeypatch.setattr(IngestService, 'MAX_FILE_SIZE_BYTES', 4)
    assert upload(client, b'12345').status_code == 413
    assert client.app.state.store.list_documents('alice') == []


def test_chat_uses_configured_gemini_client(monkeypatch, client):
    monkeypatch.setenv('USE_MOCK_CHAT', 'false')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'demo-project')
    from app.services import chat_service
    llm = MagicMock()
    llm.generate_reply.return_value = 'gemini reply'
    monkeypatch.setattr(chat_service, 'GeminiChatClient', MagicMock(return_value=llm))
    assert ask(client, conversation(client)).json()['reply'] == 'gemini reply'


def test_model_history_is_bounded_and_excludes_failed_turns():
    store = InMemoryStore()
    identifier = store.create_conversation('alice', 'Bounded')['id']
    for index in range(12):
        turn = store.start_turn('alice', identifier, f'prior-question-{index}')
        store.finish_turn('alice', identifier, turn['id'], f'prior-answer-{index}')
    failed = store.start_turn('alice', identifier, 'failed-secret')
    store.finish_turn('alice', identifier, failed['id'], None)
    llm = MagicMock()
    llm.generate_reply.return_value = 'answer'
    from app.user_models import ChatRequest
    ChatService(store, llm_client=llm).generate_reply(
        'alice', ChatRequest(conversation_id=identifier, message='current-question'))
    prompt = llm.generate_reply.call_args.args[0]
    assert 'prior-question-0"' not in prompt and 'prior-question-1"' not in prompt
    assert 'prior-question-2' in prompt and 'prior-question-11' in prompt
    assert 'failed-secret' not in prompt
    large = store.start_turn('alice', identifier, 'x' * 15000)
    store.finish_turn('alice', identifier, large['id'], 'large answer')
    ChatService(store, llm_client=llm).generate_reply(
        'alice', ChatRequest(conversation_id=identifier, message='new current'))
    assert len(llm.generate_reply.call_args.args[0]) < 12000


def test_metadata_cannot_override_ownership(client):
    response = client.post('/ingest', json={'text': 'private', 'metadata': {'user_id': 'bob'}})
    assert response.status_code == 201
    assert client.get('/get', headers={'X-User-ID': 'bob'}).json()['count'] == 0


def test_openapi_exposes_header_on_every_data_endpoint(client):
    schema = client.app.openapi()
    for path, operations in schema['paths'].items():
        for operation in operations.values():
            if path in ('/', '/health'):
                continue
            headers = [p for p in operation.get('parameters', []) if p['in'] == 'header']
            assert len(headers) == 1
            assert headers[0]['name'] == 'X-User-ID' and headers[0]['required'] is True
