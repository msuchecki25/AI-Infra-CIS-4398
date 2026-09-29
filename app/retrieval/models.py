"""Public value types returned by retrieval."""

from dataclasses import dataclass


@dataclass
class RetrievalResult:
    """A matching chunk and its normalized similarity score.

    Similarity is between 0.0 and 1.0, where a higher value is a closer
    match. Collections of results are ordered from highest to lowest score.
    """

    chunk_id: int
    document_id: str
    content: str
    similarity: float
