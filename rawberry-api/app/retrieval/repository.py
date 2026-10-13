"""In-memory vector repository used by local development and tests."""

from math import sqrt
from typing import Protocol

from .models import RetrievalResult


class RetrievalRepository(Protocol):
    def search(
        self,
        embedding: list[float],
        limit: int,
        owner_id: str | None = None,
    ) -> list[RetrievalResult]: ...


class InMemoryRetrievalRepository:
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
        self._entries[chunk_id] = (owner_id, document_id, content, list(embedding))

    def search(
        self,
        embedding: list[float],
        limit: int,
        owner_id: str | None = None,
    ) -> list[RetrievalResult]:
        if limit <= 0 or not embedding:
            return []

        query_magnitude = sqrt(sum(value * value for value in embedding))
        if not query_magnitude:
            return []

        results: list[RetrievalResult] = []
        for chunk_id, (chunk_owner_id, document_id, content, candidate) in self._entries.items():
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
            results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content=content,
                    similarity=max(0.0, min(1.0, cosine)),
                )
            )
        results.sort(key=lambda result: (-result.similarity, result.chunk_id))
        return [result for result in results if result.similarity > 0][:limit]
