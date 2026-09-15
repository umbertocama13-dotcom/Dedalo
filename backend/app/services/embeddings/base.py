"""Common interface for text embedding backends.

The matcher only depends on Embedder, so tests can use a small fake with
hand-written vectors instead of loading a real model.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np


class Embedder(ABC):
    """Turns texts into unit-length vectors, so a dot product is their cosine similarity.

    Queries (operator text) and documents (stored symptoms) have separate methods
    because some models expect a different prefix for each of them.
    """

    @abstractmethod
    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        """Embeds texts typed by the operator.

        Args:
            texts: Non-empty sequence of query texts.

        Returns:
            A float array of shape (len(texts), dimension), one unit vector per row.
        """

    @abstractmethod
    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        """Embeds texts stored in the knowledge base.

        Args:
            texts: Non-empty sequence of symptom descriptions.

        Returns:
            A float array of shape (len(texts), dimension), one unit vector per row.
        """
