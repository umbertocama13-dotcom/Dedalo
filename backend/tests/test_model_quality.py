"""Quality of the real embedding models on the fixture queries.

Slow (loads the models) and marked "model": skip with pytest -m "not model".
Both backends are checked: sentence-transformers (development) and the ONNX export
used by the desktop app; ONNX tests are skipped until scripts/export_onnx_model.py is run.
The minimums are slightly below the values measured with scripts/evaluate_matching.py
(recall 47/48, top1 40/48), so a change that makes matching clearly worse fails here.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.repositories import diagnostics_repository
from app.services.embeddings.base import Embedder
from app.services.embeddings.embedding_cache import EmbeddingCache
from app.services.embeddings.factory import create_embedder
from app.services.embeddings.onnx_embedder import OnnxEmbedder
from app.services.matching.base import MatchCandidate, MatchResult
from app.services.matching.semantic_matcher import SemanticMatcher

pytestmark = pytest.mark.model

FIXTURE = Path(__file__).parent / "fixtures" / "operator_queries.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["queries"]


def onnx_model_available() -> bool:
    return (Path(get_settings().onnx_model_dir) / "model.onnx").is_file()


@pytest.fixture(scope="session")
def sentence_transformer_embedder() -> Embedder:
    return create_embedder(get_settings().model_copy(update={"embedding_backend": "sentence-transformers"}))


@pytest.fixture(scope="session")
def onnx_embedder() -> Embedder:
    if not onnx_model_available():
        pytest.skip("ONNX model not exported: run scripts/export_onnx_model.py")
    return create_embedder(get_settings().model_copy(update={"embedding_backend": "onnx"}))


@pytest.fixture(scope="session", params=["sentence-transformers", "onnx"])
def embedder(request: pytest.FixtureRequest) -> Embedder:
    fixture_name = "onnx_embedder" if request.param == "onnx" else "sentence_transformer_embedder"
    return request.getfixturevalue(fixture_name)


@pytest.fixture
def outcomes(
    settings: Settings, test_engine: Engine, embedder: Embedder
) -> Iterator[list[tuple[dict[str, Any], list[MatchResult]]]]:
    """Runs every fixture query with the configured matcher settings."""
    matcher = SemanticMatcher(
        EmbeddingCache(embedder),
        threshold=settings.semantic_recall_threshold,
        max_results=settings.max_candidates,
        use_fuzzy=settings.semantic_use_fuzzy,
    )
    with test_engine.connect() as connection:
        yield [
            (
                case,
                matcher.match(
                    case["query"],
                    [
                        MatchCandidate(**row)
                        for row in diagnostics_repository.list_candidates(
                            connection, case["family_id"], case["cycle_phase_id"]
                        )
                    ],
                ),
            )
            for case in CASES
        ]


def ids(results: list[MatchResult]) -> list[int]:
    return [result.candidate.diagnostic_id for result in results]


def of_kind(outcomes: list[tuple[dict[str, Any], list[MatchResult]]], kind: str) -> list[tuple[dict[str, Any], list[MatchResult]]]:
    return [outcome for outcome in outcomes if outcome[0]["kind"] == kind]


def test_embeddings_are_unit_vectors(embedder: Embedder) -> None:
    vectors = np.vstack([embedder.encode_queries(["la pinza non chiude"]), embedder.encode_documents(["a", "b"])])

    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=1e-5)


def test_onnx_gives_the_same_vectors_as_sentence_transformers(
    sentence_transformer_embedder: Embedder, onnx_embedder: Embedder
) -> None:
    assert isinstance(onnx_embedder, OnnxEmbedder)
    texts = [case["query"] for case in CASES] + [
        "La cella di saldatura non completa il ciclo ed entra in allarme",
        "Il pannello operatore HMI è bloccato e non risponde al tocco",
    ]

    reference = sentence_transformer_embedder.encode_documents(texts)
    exported = onnx_embedder.encode_documents(texts)

    cosine = np.sum(reference * exported, axis=1)
    assert cosine.min() >= 0.999, f"lowest cosine {cosine.min():.5f} for «{texts[int(cosine.argmin())]}»"


def test_paraphrases_find_the_expected_diagnosis(outcomes: list[tuple[dict[str, Any], list[MatchResult]]]) -> None:
    matches = of_kind(outcomes, "match")
    found = [case["id"] for case, results in matches if set(case["expected"]) & set(ids(results))]
    first = [case["id"] for case, results in matches if results and results[0].candidate.diagnostic_id in case["expected"]]

    assert len(found) >= 46, f"missed: {sorted({case['id'] for case, _ in matches} - set(found))}"
    assert len(first) >= 38


def test_unrelated_queries_never_look_certain(
    outcomes: list[tuple[dict[str, Any], list[MatchResult]]], settings: Settings
) -> None:
    for case, results in of_kind(outcomes, "no_match"):
        assert not results or results[0].score < settings.semantic_match_threshold, case["query"]


def test_negated_queries_never_return_the_opposite_symptom(
    outcomes: list[tuple[dict[str, Any], list[MatchResult]]],
) -> None:
    for case, results in of_kind(outcomes, "negation"):
        assert not set(case["forbidden"]) & set(ids(results)), case["query"]
