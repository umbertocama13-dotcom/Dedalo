"""Deterministic stand-in for the embedding model, used by tests that must not load it.

Loading the real model takes seconds and hundreds of megabytes; its quality is
measured separately by the tests marked "model" and by scripts/evaluate_matching.py.
"""

import hashlib
from collections.abc import Sequence

import numpy as np

from app.services.embeddings.base import Embedder
from app.utils.normalize_text_ita import normalize_text_ita


class FakeEmbedder(Embedder):
    """Bag-of-words embedder: sentences sharing more words get closer vectors.

    Texts listed in ``fixed`` get exactly the given vector, so a unit test can set
    the cosine similarity it needs. Every call is recorded.
    """

    def __init__(self, fixed: dict[str, Sequence[float]] | None = None, dimension: int = 256) -> None:
        self.fixed = fixed or {}
        self.dimension = len(next(iter(self.fixed.values()))) if self.fixed else dimension
        self.query_calls: list[list[str]] = []
        self.document_calls: list[list[str]] = []

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        self.query_calls.append(list(texts))
        return np.stack([self._vector(text) for text in texts])

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        self.document_calls.append(list(texts))
        return np.stack([self._vector(text) for text in texts])

    def _vector(self, text: str) -> np.ndarray:
        if text in self.fixed:
            vector = np.array(self.fixed[text], dtype=np.float32)
        else:
            vector = np.zeros(self.dimension, dtype=np.float32)
            for word in normalize_text_ita(text).split():
                # hashlib instead of hash(): Python randomizes hash() of strings between runs.
                bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimension
                vector[bucket] += 1.0
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector
