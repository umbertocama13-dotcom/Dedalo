import threading
from collections.abc import Sequence

import numpy as np

from app.services.embeddings.base import Embedder


class EmbeddingCache:
    """Remembers the vector of every symptom text already embedded.

    The database stays the only source of truth: candidates are read from it at
    every request and only texts never seen before are embedded. There is no index
    to invalidate after a create, update or CSV import, and a symptom repeated on
    many rows is embedded once.

    Entries of edited or deleted texts are never evicted. With symptom sentences of
    a few hundred bytes and 384-768 float32 values per vector, even tens of thousands
    of historical texts stay well below the size of the model itself.
    """

    def __init__(self, embedder: Embedder) -> None:
        """Initializes an empty cache.

        Args:
            embedder: Backend used to compute missing vectors.
        """
        self._embedder = embedder
        self._vectors: dict[str, np.ndarray] = {}
        # FastAPI runs sync routes in a thread pool, so concurrent requests share this dict.
        self._lock = threading.Lock()

    def document_vectors(self, texts: Sequence[str]) -> np.ndarray:
        """Returns the vectors of stored symptom texts, computing only the missing ones.

        Args:
            texts: Symptom descriptions, duplicates allowed.

        Returns:
            An array with one row per input text, in the same order; shape (0, 0) if empty.
        """
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        with self._lock:
            missing = list(dict.fromkeys(text for text in texts if text not in self._vectors))
        if missing:
            # Computed outside the lock so a slow batch does not block other requests.
            # Two requests may embed the same new text at the same time: harmless, same result.
            vectors = self._embedder.encode_documents(missing)
            with self._lock:
                self._vectors.update(zip(missing, vectors, strict=True))

        with self._lock:
            return np.stack([self._vectors[text] for text in texts])

    def query_vector(self, text: str) -> np.ndarray:
        """Embeds an operator query. Queries are not cached: they rarely repeat.

        Args:
            text: Text typed by the operator.

        Returns:
            The query vector.
        """
        return self._embedder.encode_queries([text])[0]

    def warm_up(self, texts: Sequence[str]) -> None:
        """Pre-computes vectors so the first operator request is not slowed down.

        Args:
            texts: Symptom descriptions currently in the knowledge base.
        """
        self.document_vectors(texts)

    def __len__(self) -> int:
        """Returns the number of cached texts."""
        with self._lock:
            return len(self._vectors)
