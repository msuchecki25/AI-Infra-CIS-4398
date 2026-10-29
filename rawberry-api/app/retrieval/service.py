"""Query embedding and similarity search orchestration."""

from .embeddings import EmbeddingProvider
from .models import RetrievalResult
from .repository import RetrievalRepository


class RetrievalService:
    """Turn a text query into a vector, then delegate ranking to the repository."""

    def __init__(self, embeddings: EmbeddingProvider, repository: RetrievalRepository) -> None:
        self.embeddings = embeddings
        self.repository = repository

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        owner_id: str | None = None,
    ) -> list[RetrievalResult]:
        # Avoid embedding empty input or asking the repository for an unusable result set.
        if not query.strip() or limit <= 0:
            return []
        # The same owner scope is carried through to storage so results stay isolated.
        return self.repository.search(
            self.embeddings.embed_query(query),
            limit,
            owner_id=owner_id,
        )
