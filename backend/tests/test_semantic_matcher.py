"""Unit tests for the semantic matcher, without a database and without the real model.

Vectors are set by hand, so each test controls the cosine similarity it needs.
"""

import math

import pytest

from app.services.embeddings.embedding_cache import EmbeddingCache
from app.services.matching.base import MatchCandidate, MatchResult
from app.services.matching.semantic_matcher import SemanticMatcher
from tests.fake_embedder import FakeEmbedder

QUERY = "descrizione dell'operatore"


def unit(angle_degrees: float) -> list[float]:
    """Unit vector whose cosine similarity with [1, 0] is cos(angle)."""
    radians = math.radians(angle_degrees)
    return [math.cos(radians), math.sin(radians)]


def candidate(diagnostic_id: int, symptom: str, family_id: int | None = None, phase_id: int | None = None) -> MatchCandidate:
    return MatchCandidate(
        diagnostic_id=diagnostic_id,
        symptom_description=symptom,
        affected_component="Componente",
        probable_cause="Causa",
        recommended_solution="Soluzione",
        family_id=family_id,
        cycle_phase_id=phase_id,
    )


def matcher_for(fixed: dict[str, list[float]], threshold: float = 0.5, **kwargs: object) -> SemanticMatcher:
    return SemanticMatcher(EmbeddingCache(FakeEmbedder(fixed={QUERY: [1.0, 0.0], **fixed})), threshold, **kwargs)


def ids(results: list[MatchResult]) -> list[int]:
    return [result.candidate.diagnostic_id for result in results]


def test_results_above_threshold_are_ordered_by_score() -> None:
    matcher = matcher_for({"vicino": unit(10), "medio": unit(40), "lontano": unit(80)})
    candidates = [candidate(1, "lontano"), candidate(2, "medio"), candidate(3, "vicino")]

    results = matcher.match(QUERY, candidates)

    assert ids(results) == [3, 2]
    assert results[0].score == pytest.approx(math.cos(math.radians(10)), abs=1e-4)


def test_equal_scores_prefer_the_most_specific_scope_then_the_lowest_id() -> None:
    matcher = matcher_for({"stesso sintomo": unit(0)})
    candidates = [
        candidate(4, "stesso sintomo"),
        candidate(3, "stesso sintomo", family_id=1),
        candidate(2, "stesso sintomo"),
        candidate(1, "stesso sintomo", family_id=1, phase_id=2),
    ]

    assert ids(matcher.match(QUERY, candidates)) == [1, 3, 2, 4]


def test_max_results_keeps_only_the_best() -> None:
    matcher = matcher_for({"a": unit(5), "b": unit(10), "c": unit(15)}, max_results=2)

    assert ids(matcher.match(QUERY, [candidate(1, "c"), candidate(2, "b"), candidate(3, "a")])) == [3, 2]


def test_threshold_is_inclusive() -> None:
    matcher = matcher_for({"al limite": unit(60)}, threshold=0.5)

    assert ids(matcher.match(QUERY, [candidate(1, "al limite")])) == [1]


@pytest.mark.parametrize("query", ["", "   ", "il la di"], ids=["empty", "blank", "only-stopwords"])
def test_meaningless_query_returns_nothing_without_calling_the_model(query: str) -> None:
    embedder = FakeEmbedder(fixed={"a": [1.0, 0.0]})
    matcher = SemanticMatcher(EmbeddingCache(embedder), threshold=0.0)

    assert matcher.match(query, [candidate(1, "a")]) == []
    assert embedder.query_calls == []


def test_no_candidates_returns_nothing() -> None:
    assert matcher_for({}).match(QUERY, []) == []


def test_opposite_symptom_is_discarded_even_with_a_high_score() -> None:
    # Bag-of-words vectors: the two sentences differ only by "non" and score ~0.89.
    matcher = SemanticMatcher(EmbeddingCache(FakeEmbedder()), threshold=0.5)
    candidates = [
        candidate(1, "La pinza del robot non chiude completamente"),
        candidate(2, "La pinza del robot chiude ma non si apre"),
    ]

    results = matcher.match("La pinza del robot chiude completamente", candidates)

    assert 1 not in ids(results)


def test_fuzzy_score_rescues_a_query_with_typos() -> None:
    symptom = "Il nastro trasportatore si ferma a intermittenza"
    typo = "nastor trasportatre si ferma a intermitenza"
    fixed = {symptom: unit(0), typo: unit(80)}
    semantic_only = SemanticMatcher(EmbeddingCache(FakeEmbedder(fixed=fixed)), threshold=0.8)
    with_fuzzy = SemanticMatcher(EmbeddingCache(FakeEmbedder(fixed=fixed)), threshold=0.8, use_fuzzy=True)

    assert semantic_only.match(typo, [candidate(1, symptom)]) == []
    [result] = with_fuzzy.match(typo, [candidate(1, symptom)])
    assert result.score > 0.9


@pytest.mark.parametrize(("threshold", "max_results"), [(-0.1, 5), (1.1, 5), (0.5, 0)])
def test_invalid_configuration_is_rejected(threshold: float, max_results: int) -> None:
    with pytest.raises(ValueError):
        SemanticMatcher(EmbeddingCache(FakeEmbedder()), threshold=threshold, max_results=max_results)


@pytest.mark.parametrize(
    ("family_id", "phase_id", "scope"),
    [(None, None, "generic"), (3, None, "family"), (3, 11, "phase")],
)
def test_candidate_scope(family_id: int | None, phase_id: int | None, scope: str) -> None:
    assert candidate(1, "s", family_id=family_id, phase_id=phase_id).scope == scope


def test_candidate_can_be_built_from_a_repository_row() -> None:
    # Keys returned by diagnostics_repository.list_candidates.
    row = {
        "diagnostic_id": 30,
        "symptom_description": "Il pallet non arriva in posizione di lavoro",
        "affected_component": "Sensore presenza pallet",
        "probable_cause": "Sensore sporco.",
        "recommended_solution": "Pulire il sensore.",
        "family_id": 3,
        "cycle_phase_id": 9,
        "phase_number": 1,
        "phase_name": "Ingresso pallet",
    }

    assert MatchCandidate(**row).scope == "phase"
