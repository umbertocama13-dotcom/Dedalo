from collections.abc import Sequence

import numpy as np

from app.services.embeddings.base import Embedder


class SentenceTransformerEmbedder(Embedder):
    """Local embedding model run with sentence-transformers on CPU.

    The model is downloaded from Hugging Face on first use and then read from the
    local cache, so after the first start no text leaves the machine.
    """

    def __init__(self, model_name: str, query_prefix: str = "", document_prefix: str = "") -> None:
        """Loads the model. Meant to be called once, from create_app().

        Args:
            model_name: Hugging Face model id, e.g.
                sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2.
            query_prefix: Text prepended to queries (e5 models expect "query: ").
            document_prefix: Text prepended to documents (e5 models expect "passage: ").
        """
        # Imported here and not at module level: importing sentence_transformers loads
        # torch, which takes seconds and is not needed by tests that use a fake Embedder.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device="cpu")
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        """Embeds texts typed by the operator.

        Args:
            texts: Non-empty sequence of query texts.

        Returns:
            One unit vector per text.
        """
        return self._encode([f"{self._query_prefix}{text}" for text in texts])

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        """Embeds symptom descriptions stored in the knowledge base.

        Args:
            texts: Non-empty sequence of symptom descriptions.

        Returns:
            One unit vector per text.
        """
        return self._encode([f"{self._document_prefix}{text}" for text in texts])

    def _encode(self, texts: list[str]) -> np.ndarray:
        """Runs the model with unit-length normalization.

        Args:
            texts: Already prefixed texts.

        Returns:
            A float32 array with one normalized vector per text.
        """
        return self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
