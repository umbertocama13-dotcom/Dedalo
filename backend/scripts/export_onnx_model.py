"""Exports the sentence embedding model to ONNX, for the desktop app (no PyTorch at runtime).

Build tool, not used by the application. It needs PyTorch and optimum-onnx, which are
not in requirements.txt and conflict with its transformers version: run it in a separate
virtual environment (from the backend/ folder):

    python3 -m venv .venv-export
    .venv-export/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
    .venv-export/bin/pip install optimum-onnx onnxruntime
    .venv-export/bin/python scripts/export_onnx_model.py

The output folder contains model.onnx, tokenizer.json and dedalo_embedding.json with the
pooling settings read from the sentence-transformers configuration of the model.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
from optimum.exporters.onnx import main_export

DEFAULT_MODEL = "nickprock/sentence-bert-base-italian-xxl-uncased"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "models" / "sentence-bert-base-italian-xxl-uncased"
# Modules OnnxEmbedder can reproduce: the transformer, mean pooling and L2 normalization.
SUPPORTED_MODULES = {
    "sentence_transformers.models.Transformer",
    "sentence_transformers.models.Pooling",
    "sentence_transformers.models.Normalize",
}


def read_model_json(model: str, filename: str) -> Any:
    """Reads a JSON file of the model from the Hugging Face cache (downloading it if needed).

    Args:
        model: Hugging Face model id.
        filename: File path inside the model repository.

    Returns:
        The parsed JSON content.
    """
    return json.loads(Path(hf_hub_download(model, filename)).read_text(encoding="utf-8"))


def check_supported(model: str) -> int:
    """Verifies that the model uses only what OnnxEmbedder reproduces.

    Args:
        model: Hugging Face model id.

    Returns:
        The max_seq_length of the model.

    Raises:
        SystemExit: If the model has other modules (e.g. Dense) or a pooling other than mean.
    """
    module_types = {module["type"] for module in read_model_json(model, "modules.json")}
    if not module_types <= SUPPORTED_MODULES:
        raise SystemExit(f"Unsupported sentence-transformers modules: {sorted(module_types - SUPPORTED_MODULES)}")

    pooling = read_model_json(model, "1_Pooling/config.json")
    other_modes = ("pooling_mode_cls_token", "pooling_mode_max_tokens", "pooling_mode_mean_sqrt_len_tokens")
    if not pooling.get("pooling_mode_mean_tokens") or any(pooling.get(mode) for mode in other_modes):
        raise SystemExit(f"Only mean pooling is supported, got {pooling}")

    return int(read_model_json(model, "sentence_bert_config.json")["max_seq_length"])


def main() -> None:
    """Parses arguments, checks the model and exports it."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    max_seq_length = check_supported(args.model)
    main_export(args.model, output=args.output, task="feature-extraction", device="cpu")
    settings = {"source_model": args.model, "pooling": "mean", "max_seq_length": max_seq_length}
    (args.output / "dedalo_embedding.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"Exported {args.model} to {args.output}: {sorted(path.name for path in args.output.iterdir())}")


if __name__ == "__main__":
    main()
