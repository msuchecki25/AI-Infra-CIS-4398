"""Bridge owner-scoped API chunks to the Stage 1 lexical-vector retrieval API.

These deterministic hash vectors are generated locally, not model embeddings or
persisted pgvector indexes. Both storage adapters use the same ranking path.
"""
from typing import Any

from .embeddings import HashEmbeddingProvider
from .repository import InMemoryRetrievalRepository
from .service import RetrievalService


def search_owned_chunks(
    user_id: str, chunks: list[dict[str, Any]], query: str, limit: int = 3,
) -> list[dict[str, Any]]:
    if not query.strip() or limit <= 0:
        return []
    embeddings = HashEmbeddingProvider()
    repository = InMemoryRetrievalRepository()
    for index, chunk in enumerate(chunks):
        repository.upsert(index, chunk['document_id'], chunk['text'],
                          embeddings.embed_document(chunk['text']), owner_id=user_id)
    results = RetrievalService(embeddings, repository).retrieve(query, limit, owner_id=user_id)
    return [{**chunks[result.chunk_id], 'similarity': result.similarity} for result in results]
