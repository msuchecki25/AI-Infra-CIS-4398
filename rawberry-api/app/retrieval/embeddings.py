"""Embedding contracts and a deterministic local feature-hash provider."""

from hashlib import blake2b
import math
import re
from typing import Protocol


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
