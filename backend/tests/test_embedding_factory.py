from pathlib import Path

import pytest

from app.config import Settings
from app.services.embeddings.factory import create_embedder
from app.services.embeddings.onnx_embedder import OnnxEmbedder


def test_onnx_backend_without_exported_model_fails_with_a_clear_message(settings: Settings, tmp_path: Path) -> None:
    onnx_settings = settings.model_copy(update={"embedding_backend": "onnx", "onnx_model_dir": str(tmp_path)})

    with pytest.raises(FileNotFoundError, match="export_onnx_model.py"):
        create_embedder(onnx_settings)


def test_onnx_embedder_checks_the_folder_before_loading_anything(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=str(tmp_path)):
        OnnxEmbedder(tmp_path)
