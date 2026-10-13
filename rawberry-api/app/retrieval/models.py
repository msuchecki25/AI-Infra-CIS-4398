from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalResult:
    """A matching chunk and its normalized similarity score."""

    chunk_id: int
    document_id: str
    content: str
    similarity: float
