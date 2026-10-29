"""Vertex AI semantic embeddings and deterministic local embeddings for development."""

from hashlib import blake2b
import math
import re
from typing import Protocol

from app.config import Settings, get_settings

# Keep this pair pinned: changing either value requires re-embedding stored chunks.
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


class VertexEmbeddingProvider:
    """Use the same pinned model and dimensions for stored chunks and queries."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def embed_query(self, text: str) -> list[float]:
        # Questions and source passages use different retrieval tasks within the same vector space.
        return self._embed(text, "RETRIEVAL_QUERY")

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_DOCUMENT")

    def _embed(self, text: str, task_type: str) -> list[float]:
        from google import genai

        if not text.strip():
            raise ValueError("Cannot embed empty text")
        if not self.settings.google_cloud_project:
            raise ValueError("Set GOOGLE_CLOUD_PROJECT before using Vertex AI embeddings")
        # Vertex AI uses Application Default Credentials, including Cloud Run's service account.
        with genai.Client(
            vertexai=True,
            project=self.settings.google_cloud_project,
            location=self.settings.google_cloud_location,
        ) as client:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config={
                    "task_type": task_type,
                    "output_dimensionality": EMBEDDING_DIMENSIONS,
                    # Truncated text would produce a vector for only part of the stored passage.
                    "auto_truncate": False,
                },
            )
        if not response.embeddings or len(response.embeddings) != 1:
            raise ValueError("Vertex AI must return one embedding")
        vector = response.embeddings[0].values
        validate_embedding(vector)
        return list(vector)


def validate_embedding(vector: list[float] | None) -> None:
    """Reject incompatible or unusable vectors before sending them to pgvector."""
    if (
        not vector
        or len(vector) != EMBEDDING_DIMENSIONS
        or not all(math.isfinite(value) for value in vector)
        or not any(vector)
    ):
        raise ValueError("Expected a finite, nonzero 768-dimensional embedding")


class EmbeddingProvider(Protocol):
    def embed_query(self, text: str) -> list[float]: ...

    def embed_document(self, text: str) -> list[float]: ...


class HashEmbeddingProvider:
    """Create stable lexical vectors without network calls or model weights."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 16:
            raise ValueError("dimensions must be at least 16")
        self.dimensions = dimensions

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        words = re.findall(r"[a-z0-9]+", text.lower())
        features = words + [f"{left}_{right}" for left, right in zip(words, words[1:])]
        for feature in features:
            digest = blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            vector[index] += 1.0 if value & (1 << 63) else -1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        return [value / magnitude for value in vector] if magnitude else vector
