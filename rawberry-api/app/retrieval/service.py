"""Query embedding and similarity search orchestration."""

from .embeddings import EmbeddingProvider
from .models import RetrievalResult
from .repository import RetrievalRepository


class RetrievalService:
    def __init__(self, embeddings: EmbeddingProvider, repository: RetrievalRepository) -> None:
        self.embeddings = embeddings
        self.repository = repository

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        owner_id: str | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip() or limit <= 0:
            return []
        return self.repository.search(
            self.embeddings.embed_query(query),
            limit,
            owner_id=owner_id,
        )
