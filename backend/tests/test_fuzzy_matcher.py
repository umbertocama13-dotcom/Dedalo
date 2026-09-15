"""Unit tests for the v1 fuzzy matcher, kept as evaluation baseline, without a database.

Candidates mirror rows of database/seed.sql.
"""

import pytest

from app.services.matching.base import MatchCandidate, MatchResult
from app.services.matching.fuzzy_matcher import FuzzyMatcher, fuzzy_score

CONVEYOR_SYMPTOM = "Il nastro trasportatore si ferma a intermittenza"


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


@pytest.fixture
def candidates() -> list[MatchCandidate]:
    return [
        candidate(1, CONVEYOR_SYMPTOM),
        candidate(2, CONVEYOR_SYMPTOM),
        candidate(11, "La pinza del robot non chiude completamente", family_id=1),
        candidate(19, "Saldatura del film irregolare con grinze", family_id=2),
    ]


@pytest.fixture
def matcher() -> FuzzyMatcher:
    return FuzzyMatcher(threshold=0.8)


def ids(results: list[MatchResult]) -> list[int]:
    return [result.candidate.diagnostic_id for result in results]


def test_fuzzy_score_range() -> None:
    assert fuzzy_score(CONVEYOR_SYMPTOM, CONVEYOR_SYMPTOM) == 1.0
    assert fuzzy_score("Il motore fa fumo", CONVEYOR_SYMPTOM) < 0.5


def test_exact_symptom_returns_every_row_with_that_symptom(matcher: FuzzyMatcher, candidates: list[MatchCandidate]) -> None:
    results = matcher.match(CONVEYOR_SYMPTOM, candidates)

    assert ids(results) == [1, 2]
    assert all(result.score == 1.0 for result in results)


@pytest.mark.parametrize(
    "query",
    [
        "nastro trasportatre si ferma a intermitenza",
        "si ferma a intermittenza il nastro trasportatore",
        "il nastro trasportatore della linea 3 si ferma a intermittenza",
        "IL NASTRO TRASPORTATORE SI FERMA, A INTERMITTENZA!",
    ],
    ids=["typos", "word-order", "extra-words", "case-and-punctuation"],
)
def test_query_variants_still_match(matcher: FuzzyMatcher, candidates: list[MatchCandidate], query: str) -> None:
    assert ids(matcher.match(query, candidates)) == [1, 2]


@pytest.mark.parametrize(
    "query",
    ["Il nastro trasportatore è rumoroso", "nastro", "Il motore fa fumo", "il la di", ""],
    ids=["same-component-different-symptom", "single-keyword", "unrelated", "only-stopwords", "empty"],
)
def test_queries_without_a_close_string_return_nothing(
    matcher: FuzzyMatcher, candidates: list[MatchCandidate], query: str
) -> None:
    assert matcher.match(query, candidates) == []


def test_partial_description_is_the_v1_limit(candidates: list[MatchCandidate]) -> None:
    # The limit that motivated v2: a shorter description scores ~0.62 and finds nothing at 0.80.
    assert FuzzyMatcher(threshold=0.8).match("pinza non chiude", candidates) == []
    assert ids(FuzzyMatcher(threshold=0.6).match("pinza non chiude", candidates)) == [11]


def test_ties_prefer_the_most_specific_scope_and_max_results_applies() -> None:
    rows = [candidate(3, CONVEYOR_SYMPTOM), candidate(2, CONVEYOR_SYMPTOM, family_id=1), candidate(1, CONVEYOR_SYMPTOM, 1, 2)]

    assert ids(FuzzyMatcher(threshold=0.8, max_results=2).match(CONVEYOR_SYMPTOM, rows)) == [1, 2]


@pytest.mark.parametrize(("threshold", "max_results"), [(-0.1, 5), (1.1, 5), (0.8, 0)])
def test_invalid_configuration_is_rejected(threshold: float, max_results: int) -> None:
    with pytest.raises(ValueError):
        FuzzyMatcher(threshold=threshold, max_results=max_results)
