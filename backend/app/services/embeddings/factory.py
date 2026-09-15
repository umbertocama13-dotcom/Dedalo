from pathlib import Path

from app.config import Settings
from app.services.embeddings.base import Embedder


def create_embedder(settings: Settings) -> Embedder:
    """Instantiates the embedding backend selected by EMBEDDING_BACKEND.

    Args:
        settings: Application settings.

    Returns:
        The embedder, typed as the Embedder interface.

    Raises:
        FileNotFoundError: If EMBEDDING_BACKEND=onnx and the exported model is missing.
    """
    if settings.embedding_backend == "onnx":
        from app.services.embeddings.onnx_embedder import OnnxEmbedder

        return OnnxEmbedder(
            Path(settings.onnx_model_dir), settings.embedding_query_prefix, settings.embedding_document_prefix
        )

    from app.services.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(
        settings.embedding_model, settings.embedding_query_prefix, settings.embedding_document_prefix
    )
