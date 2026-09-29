"""Public API for retrieving relevant document chunks."""

from .models import RetrievalResult
from .service import RetrievalService

__all__ = ["RetrievalResult", "RetrievalService"]
