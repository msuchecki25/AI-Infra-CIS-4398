"""Retrieval orchestration exposed to application callers."""

from .models import RetrievalResult


class RetrievalService:
    """Coordinate query embedding and similarity search.

    Infrastructure dependencies and orchestration will be added in a later
    stage without changing the package's public boundary.
    """

    def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> list[RetrievalResult]:
        """Return the chunks most relevant to ``query``.

        Raises:
            NotImplementedError: Retrieval orchestration is not implemented.
        """
        raise NotImplementedError("Retrieval is not implemented yet")
