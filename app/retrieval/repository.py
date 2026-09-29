"""Internal contract for retrieval persistence."""

from typing import Protocol

from .models import RetrievalResult


class RetrievalRepository(Protocol):
    """Find document chunks that are most similar to an embedding."""

    def search(
        self,
        embedding: list[float],
        limit: int,
    ) -> list[RetrievalResult]:
        """Return up to ``limit`` results ordered by descending similarity."""
        ...
