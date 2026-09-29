"""Internal contract for producing retrieval embeddings."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Produce vector representations for queries and document chunks."""

    def embed_query(self, text: str) -> list[float]:
        """Return an embedding for a retrieval query."""
        ...

    def embed_document(self, text: str) -> list[float]:
        """Return an embedding for a document chunk."""
        ...
