from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.postgres_repository import PostgresRepository
from app.repository import StorageError
from app.retrieval.embeddings import (
    EMBEDDING_MODEL, VertexEmbeddingProvider, validate_embedding,
)


def test_vertex_uses_pinned_model_task_types_and_dimensions(monkeypatch):
    client = MagicMock()
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[1.0] + [0.0] * 767)],
    )
    constructor = MagicMock()
    constructor.return_value.__enter__.return_value = client
    monkeypatch.setattr('google.genai.Client', constructor)
    provider = VertexEmbeddingProvider(Settings(google_cloud_project='test-project', google_cloud_location='us-central1'))
    assert len(provider.embed_document('document text')) == 768
    assert len(provider.embed_query('question')) == 768
    constructor.assert_called_with(vertexai=True, project='test-project', location='us-central1')
    calls = client.models.embed_content.call_args_list
    assert [call.kwargs['config']['task_type'] for call in calls] == ['RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY']
    assert all(call.kwargs['model'] == EMBEDDING_MODEL for call in calls)
    assert all(call.kwargs['config']['output_dimensionality'] == 768 for call in calls)
    assert all(call.kwargs['config']['auto_truncate'] is False for call in calls)


@pytest.mark.parametrize('vector', [None, [], [1.0] * 256, [0.0] * 768,
                                   [float('nan')] * 768, [float('inf')] * 768])
def test_invalid_vectors_are_rejected(vector):
    with pytest.raises(ValueError):
        validate_embedding(vector)


def test_missing_project_fails_before_creating_a_client(monkeypatch):
    constructor = MagicMock()
    monkeypatch.setattr('google.genai.Client', constructor)
    with pytest.raises(ValueError, match='GOOGLE_CLOUD_PROJECT'):
        VertexEmbeddingProvider(Settings()).embed_query('question')
    constructor.assert_not_called()


def test_failed_embedding_batch_never_opens_database(monkeypatch):
    provider = MagicMock()
    provider.embed_document.side_effect = [[1.0] + [0.0] * 767, RuntimeError('provider private details')]
    repository = PostgresRepository('unused', embeddings=provider)
    connection = MagicMock()
    monkeypatch.setattr(repository, '_connection', connection)
    with pytest.raises(StorageError, match='Embedding generation failed'):
        repository.save_documents('alice', [({}, b'text', [{'text': 'first'}, {'text': 'second'}])])
    connection.assert_not_called()


def test_search_uses_query_embeddings_and_safe_sql_parameters(monkeypatch):
    provider = MagicMock()
    provider.embed_query.return_value = [1.0] + [0.0] * 767
    repository = PostgresRepository('unused', embeddings=provider)
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = [{'text': 'result'}]

    @contextmanager
    def connect():
        yield connection

    monkeypatch.setattr(repository, '_connection', connect)
    owner = "alice' OR TRUE --"
    assert repository.search_chunks(owner, 'question', 2) == [{'text': 'result'}]
    statement, parameters = connection.execute.call_args.args
    assert owner not in statement
    assert 'd.user_id = %s' in statement
    assert parameters[2:] == (owner, EMBEDDING_MODEL, 2)
    provider.embed_query.assert_called_once_with('question')
    provider.embed_document.assert_not_called()
    provider.reset_mock()
    assert repository.search_chunks('alice', ' ') == []
    assert repository.search_chunks('alice', 'question', 0) == []
    provider.embed_query.assert_not_called()
