"""Unit tests for the fuzzy matcher, without a database.

Candidates mirror the rows of database/seed.sql, so these known cases match the
integration tests that later run on the real test database.
"""

import dataclasses

import pytest

from app.services.matching.fuzzy_matcher import FuzzyMatcher, MatchCandidate, MatchResult

CONVEYOR_SYMPTOM = "Il nastro trasportatore si ferma a intermittenza"


@pytest.fixture
def conveyor_photocell() -> MatchCandidate:
    return MatchCandidate(
        base_diagnostic_id=1,
        symptom_description=CONVEYOR_SYMPTOM,
        affected_component="Nastro trasportatore di alimentazione",
        probable_cause="Fotocellula di presenza pezzo sporca o disallineata.",
        recommended_solution="Pulire e riallineare la fotocellula.",
    )


@pytest.fixture
def conveyor_overload() -> MatchCandidate:
    return MatchCandidate(
        base_diagnostic_id=2,
        symptom_description=CONVEYOR_SYMPTOM,
        affected_component="Nastro trasportatore di alimentazione",
        probable_cause="Intervento della protezione termica dell'inverter.",
        recommended_solution="Verificare cinghia e cuscinetti, ripristinare l'allarme.",
    )


@pytest.fixture
def gripper() -> MatchCandidate:
    return MatchCandidate(
        base_diagnostic_id=3,
        symptom_description="La pinza del robot non chiude completamente",
        affected_component="Pinza pneumatica end-effector",
        probable_cause="Pressione dell'aria insufficiente.",
        recommended_solution="Verificare il regolatore a 6 bar.",
    )


@pytest.fixture
def sealing() -> MatchCandidate:
    return MatchCandidate(
        base_diagnostic_id=4,
        symptom_description="Saldatura del film irregolare con grinze",
        affected_component="Ganasce saldanti trasversali",
        probable_cause="Termocoppia degradata.",
        recommended_solution="Sostituire la termocoppia.",
    )


@pytest.fixture
def candidates(
    conveyor_photocell: MatchCandidate,
    conveyor_overload: MatchCandidate,
    gripper: MatchCandidate,
    sealing: MatchCandidate,
) -> list[MatchCandidate]:
    return [conveyor_photocell, conveyor_overload, gripper, sealing]


@pytest.fixture
def matcher() -> FuzzyMatcher:
    return FuzzyMatcher(threshold=80.0)


def ids(results: list[MatchResult]) -> list[int]:
    return [result.base_diagnostic_id for result in results]


# --- Queries that must match -------------------------------------------------


def test_exact_symptom_returns_every_row_with_that_symptom(
    matcher: FuzzyMatcher, candidates: list[MatchCandidate]
) -> None:
    results = matcher.match(CONVEYOR_SYMPTOM, candidates)

    assert ids(results) == [1, 2]
    assert all(result.score == 100.0 for result in results)
    assert all(result.source == "base" for result in results)


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


def test_base_result_exposes_generic_cause_and_solution(
    matcher: FuzzyMatcher, sealing: MatchCandidate
) -> None:
    [result] = matcher.match("saldatura del film irregolare con grinse", [sealing])

    assert result.cause == sealing.probable_cause
    assert result.solution == sealing.recommended_solution
    assert result.affected_component == sealing.affected_component
    assert result.exception_id is None


# --- Queries that must NOT match (anti-hallucination) ------------------------


@pytest.mark.parametrize(
    "query",
    [
        "Il nastro trasportatore è rumoroso",
        "nastro",
        "Il motore fa fumo",
        "il la di",
        "",
    ],
    ids=["same-component-different-symptom", "single-keyword", "unrelated", "only-stopwords", "empty"],
)
def test_queries_without_a_certain_match_return_nothing(
    matcher: FuzzyMatcher, candidates: list[MatchCandidate], query: str
) -> None:
    assert matcher.match(query, candidates) == []


def test_partial_description_below_threshold_returns_nothing(
    matcher: FuzzyMatcher, candidates: list[MatchCandidate]
) -> None:
    # Known trade-off of token_sort_ratio: a much shorter description scores ~62.
    # A "no data" answer is preferred over guessing a diagnosis.
    assert matcher.match("pinza non chiude", candidates) == []


def test_no_candidates_returns_nothing(matcher: FuzzyMatcher) -> None:
    assert matcher.match(CONVEYOR_SYMPTOM, []) == []


# --- Context-specific exceptions ---------------------------------------------


def test_exception_overrides_cause_and_solution(matcher: FuzzyMatcher, gripper: MatchCandidate) -> None:
    with_exception = dataclasses.replace(
        gripper,
        exception_id=1,
        specific_cause="Sensore di finecorsa spostato.",
        specific_solution="Riposizionare il sensore.",
    )

    [result] = matcher.match("La pinza del robot non chiude completamente", [with_exception])

    assert result.source == "exception"
    assert result.exception_id == 1
    assert result.base_diagnostic_id == 3
    assert result.cause == "Sensore di finecorsa spostato."
    assert result.solution == "Riposizionare il sensore."


def test_exception_on_one_duplicate_row_leaves_the_other_unchanged(
    matcher: FuzzyMatcher, conveyor_photocell: MatchCandidate, conveyor_overload: MatchCandidate
) -> None:
    overload_with_exception = dataclasses.replace(
        conveyor_overload,
        exception_id=3,
        specific_cause="Freno dello svolgitore troppo serrato.",
        specific_solution="Ridurre la coppia del freno.",
    )

    results = matcher.match(CONVEYOR_SYMPTOM, [conveyor_photocell, overload_with_exception])

    by_id = {result.base_diagnostic_id: result for result in results}
    assert by_id[1].source == "base"
    assert by_id[1].cause == conveyor_photocell.probable_cause
    assert by_id[2].source == "exception"
    assert by_id[2].cause == "Freno dello svolgitore troppo serrato."


# --- Ordering and configuration ----------------------------------------------


def test_results_are_ordered_by_score_then_by_id(
    matcher: FuzzyMatcher, conveyor_photocell: MatchCandidate, conveyor_overload: MatchCandidate
) -> None:
    similar = dataclasses.replace(
        conveyor_photocell,
        base_diagnostic_id=9,
        symptom_description="Il nastro trasportatore si ferma spesso a intermittenza",
    )

    results = matcher.match(CONVEYOR_SYMPTOM, [similar, conveyor_overload, conveyor_photocell])

    assert ids(results) == [1, 2, 9]
    assert results[0].score >= results[1].score > results[2].score >= 80.0


def test_threshold_is_configurable(candidates: list[MatchCandidate]) -> None:
    permissive = FuzzyMatcher(threshold=60.0)

    assert ids(permissive.match("pinza non chiude", candidates)) == [3]


@pytest.mark.parametrize("threshold", [-1.0, 100.1])
def test_threshold_outside_score_range_is_rejected(threshold: float) -> None:
    with pytest.raises(ValueError):
        FuzzyMatcher(threshold=threshold)


def test_candidate_can_be_built_from_a_repository_row() -> None:
    # Keys returned by diagnostics_repository.list_match_candidates.
    row = {
        "base_diagnostic_id": 4,
        "symptom_description": "Saldatura del film irregolare con grinze",
        "affected_component": "Ganasce saldanti trasversali",
        "probable_cause": "Termocoppia degradata.",
        "recommended_solution": "Sostituire la termocoppia.",
        "exception_id": 2,
        "specific_cause": "Usura del PTFE.",
        "specific_solution": "Sostituire il nastro in PTFE.",
    }

    assert MatchCandidate(**row).exception_id == 2
