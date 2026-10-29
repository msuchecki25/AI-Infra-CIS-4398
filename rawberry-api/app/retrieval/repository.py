"""In-memory vector repository used by local development and tests."""

from math import sqrt
from typing import Protocol

from .models import RetrievalResult


class RetrievalRepository(Protocol):
    """Search contract used by the retrieval service, independent of storage type."""

    def search(
        self,
        embedding: list[float],
        limit: int,
        owner_id: str | None = None,
    ) -> list[RetrievalResult]: ...


class InMemoryRetrievalRepository:
    """Store chunk embeddings locally and rank them with cosine similarity."""

    def __init__(self) -> None:
        self._entries: dict[int, tuple[str | None, str, str, list[float]]] = {}

    def upsert(
        self,
        chunk_id: int,
        document_id: str,
        content: str,
        embedding: list[float],
        owner_id: str | None = None,
    ) -> None:
        # Copy the vector so later changes by the caller cannot alter stored data.
        self._entries[chunk_id] = (owner_id, document_id, content, list(embedding))

    def search(
        self,
        embedding: list[float],
        limit: int,
        owner_id: str | None = None,
    ) -> list[RetrievalResult]:
        if limit <= 0 or not embedding:
            return []

        # Cosine similarity is undefined for a zero-length vector.
        query_magnitude = sqrt(sum(value * value for value in embedding))
        if not query_magnitude:
            return []

        results: list[RetrievalResult] = []
        for chunk_id, (chunk_owner_id, document_id, content, candidate) in self._entries.items():
            # Keep each search within the caller's owner scope; vectors must share dimensions.
            if chunk_owner_id != owner_id:
                continue
            if len(candidate) != len(embedding):
                continue
            candidate_magnitude = sqrt(sum(value * value for value in candidate))
            if not candidate_magnitude:
                continue
            cosine = sum(a * b for a, b in zip(embedding, candidate)) / (
                query_magnitude * candidate_magnitude
            )
            # Similarity is exposed as a 0..1 score; negative matches are dropped below.
            results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content=content,
                    similarity=max(0.0, min(1.0, cosine)),
                )
            )
        # Chunk ID makes equal-score ordering stable across repeated searches.
        results.sort(key=lambda result: (-result.similarity, result.chunk_id))
        return [result for result in results if result.similarity > 0][:limit]
