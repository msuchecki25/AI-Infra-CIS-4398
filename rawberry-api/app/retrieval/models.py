from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalResult:
    """One matching text chunk and its similarity score.

    Frozen results can be safely passed between retrieval and chat code without
    allowing one caller to mutate another caller's match.
    """

    chunk_id: int
    document_id: str
    content: str
    similarity: float
