import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from app.services.embeddings.base import Embedder


class OnnxEmbedder(Embedder):
    """Embedding model run with ONNX Runtime, without PyTorch (desktop app).

    Reproduces what sentence-transformers does for a Transformer + mean Pooling model:
    tokenization, forward pass, average of the token vectors weighted by the attention
    mask, L2 normalization. The model folder is produced by scripts/export_onnx_model.py.
    """

    def __init__(
        self, model_dir: Path, query_prefix: str = "", document_prefix: str = "", batch_size: int = 32
    ) -> None:
        """Loads tokenizer and ONNX session. Meant to be called once, from create_app().

        Args:
            model_dir: Folder with model.onnx, tokenizer.json and dedalo_embedding.json.
            query_prefix: Text prepended to queries.
            document_prefix: Text prepended to documents.
            batch_size: Texts encoded per forward pass.

        Raises:
            FileNotFoundError: If the folder does not contain an exported model.
        """
        model_file = model_dir / "model.onnx"
        if not model_file.is_file():
            raise FileNotFoundError(f"ONNX model not found in {model_dir}: run scripts/export_onnx_model.py first")

        # Imported here: the development app uses sentence-transformers and does not need them.
        import onnxruntime
        from tokenizers import Tokenizer

        config = json.loads((model_dir / "dedalo_embedding.json").read_text(encoding="utf-8"))
        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=config["max_seq_length"])
        # Pads each batch to its longest text; the attention mask excludes padding from the average.
        self._tokenizer.enable_padding(pad_id=self._tokenizer.token_to_id("[PAD]") or 0, pad_token="[PAD]")
        self._session = onnxruntime.InferenceSession(str(model_file), providers=["CPUExecutionProvider"])
        self._input_names = {model_input.name for model_input in self._session.get_inputs()}
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        self._batch_size = batch_size

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
        """Runs tokenizer, model, mean pooling and normalization in batches.

        Args:
            texts: Already prefixed texts.

        Returns:
            A float32 array with one normalized vector per text.
        """
        batches = []
        for start in range(0, len(texts), self._batch_size):
            encodings = self._tokenizer.encode_batch(texts[start : start + self._batch_size])
            attention_mask = np.array([encoding.attention_mask for encoding in encodings], dtype=np.int64)
            feeds = {
                "input_ids": np.array([encoding.ids for encoding in encodings], dtype=np.int64),
                "attention_mask": attention_mask,
            }
            if "token_type_ids" in self._input_names:
                feeds["token_type_ids"] = np.array([encoding.type_ids for encoding in encodings], dtype=np.int64)

            # First output: one vector per token, shape (batch, tokens, dimension).
            token_vectors = self._session.run(None, feeds)[0]
            mask = attention_mask[:, :, np.newaxis].astype(np.float32)
            # Clipped to avoid a division by zero for an input made only of padding.
            mean = (token_vectors * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            batches.append(mean / np.clip(np.linalg.norm(mean, axis=1, keepdims=True), 1e-12, None))
        return np.vstack(batches).astype(np.float32)
