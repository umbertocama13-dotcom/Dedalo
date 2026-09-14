"""Integration tests for the diagnosis flow on the seeded test database.

Known cases come from database/seed.sql:
- diagnostics 1 and 2 share the conveyor symptom; exception 3 overrides 2 in family 2 / phase 5;
- diagnostic 3 (gripper) is overridden by exception 1 in family 1 / phase 2;
- diagnostic 4 (sealing) is overridden by exception 2 in family 2 / phase 7.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection

from app.repositories import diagnostics_repository
from app.schemas.diagnosis import DiagnosisRequest
from app.services.ai.base import AIProvider, AIProviderError
from app.services.ai.noop_provider import NoopAIProvider
from app.services.diagnosis_service import diagnose
from app.services.matching.fuzzy_matcher import FuzzyMatcher

CONVEYOR = "Il nastro trasportatore si ferma a intermittenza"
GRIPPER = "La pinza del robot non chiude completamente"


class StubAIProvider(AIProvider):
    """Stand-in for the external model: returns a fixed answer or fails, and records calls."""

    def __init__(self, output: str = "", fail: bool = False) -> None:
        self.output = output
        self.fail = fail
        self.calls: list[str] = []

    def normalize_symptom(self, text: str) -> str:
        self.calls.append(text)
        if self.fail:
            raise AIProviderError("model unavailable")
        return self.output


@pytest.fixture
def matcher() -> FuzzyMatcher:
    return FuzzyMatcher(threshold=80.0)


@pytest.fixture
def noop() -> NoopAIProvider:
    return NoopAIProvider()


def request(symptom: str, family_id: int, cycle_phase_id: int) -> DiagnosisRequest:
    return DiagnosisRequest(symptom=symptom, family_id=family_id, cycle_phase_id=cycle_phase_id)


# --- Matches from the knowledge base ------------------------------------------


def test_duplicate_symptom_returns_both_hypotheses(
    db_connection: Connection, matcher: FuzzyMatcher, noop: NoopAIProvider
) -> None:
    response = diagnose(db_connection, request(CONVEYOR, 1, 1), matcher, noop)

    assert response.status == "match"
    assert response.matched_on == "original"
    assert [h.base_diagnostic_id for h in response.hypotheses] == [1, 2]
    assert all(h.source == "base" for h in response.hypotheses)


def test_exception_applies_only_to_its_row_in_its_context(
    db_connection: Connection, matcher: FuzzyMatcher, noop: NoopAIProvider
) -> None:
    response = diagnose(db_connection, request(CONVEYOR, 2, 5), matcher, noop)

    by_id = {h.base_diagnostic_id: h for h in response.hypotheses}
    assert (by_id[1].source, by_id[1].exception_id) == ("base", None)
    assert (by_id[2].source, by_id[2].exception_id) == ("exception", 3)
    assert by_id[2].cause.startswith("Freno dello svolgitore")


@pytest.mark.parametrize(
    ("family_id", "cycle_phase_id", "expected_source", "cause_start"),
    [(1, 2, "exception", "Sensore magnetico"), (1, 3, "base", "Pressione dell'aria")],
    ids=["phase-with-exception", "phase-without-exception"],
)
def test_same_symptom_changes_cause_with_the_phase(
    db_connection: Connection,
    matcher: FuzzyMatcher,
    noop: NoopAIProvider,
    family_id: int,
    cycle_phase_id: int,
    expected_source: str,
    cause_start: str,
) -> None:
    response = diagnose(db_connection, request(GRIPPER, family_id, cycle_phase_id), matcher, noop)

    [hypothesis] = response.hypotheses
    assert hypothesis.source == expected_source
    assert hypothesis.cause.startswith(cause_start)


def test_knowledge_base_changes_are_visible_immediately(
    db_connection: Connection, matcher: FuzzyMatcher, noop: NoopAIProvider
) -> None:
    new_id = diagnostics_repository.insert_base_diagnostic(
        db_connection, "Il robot emette un allarme di collisione", "Robot", "Causa", "Soluzione", 1
    )

    response = diagnose(db_connection, request("il robot emette allarme di collisione", 1, 3), matcher, noop)

    assert [h.base_diagnostic_id for h in response.hypotheses] == [new_id]


# --- No match: declare missing data, never invent ------------------------------


def test_unknown_symptom_declares_missing_data(
    db_connection: Connection, matcher: FuzzyMatcher, noop: NoopAIProvider
) -> None:
    response = diagnose(db_connection, request("Il motore fa fumo", 1, 1), matcher, noop)

    assert response.status == "no_match"
    assert response.hypotheses == []
    assert response.matched_on is None
    assert response.message


# --- Context validation -------------------------------------------------------


@pytest.mark.parametrize(
    ("family_id", "cycle_phase_id", "expected_status"),
    [(999, 1, 404), (1, 999, 404), (1, 7, 400)],
    ids=["unknown-family", "unknown-phase", "phase-of-another-family"],
)
def test_invalid_context_is_rejected(
    db_connection: Connection,
    matcher: FuzzyMatcher,
    noop: NoopAIProvider,
    family_id: int,
    cycle_phase_id: int,
    expected_status: int,
) -> None:
    with pytest.raises(HTTPException) as error:
        diagnose(db_connection, request(CONVEYOR, family_id, cycle_phase_id), matcher, noop)

    assert error.value.status_code == expected_status


# --- AI provider is only a fallback --------------------------------------------


def test_ai_is_not_called_when_the_original_text_matches(db_connection: Connection, matcher: FuzzyMatcher) -> None:
    ai = StubAIProvider(output="testo che non deve essere usato")

    response = diagnose(db_connection, request(CONVEYOR, 1, 1), matcher, ai)

    assert ai.calls == []
    assert response.matched_on == "original"


def test_ai_rewrite_is_used_when_the_original_text_does_not_match(
    db_connection: Connection, matcher: FuzzyMatcher
) -> None:
    ai = StubAIProvider(output=GRIPPER)

    response = diagnose(db_connection, request("boh la pinza fa cilecca", 1, 3), matcher, ai)

    assert ai.calls == ["boh la pinza fa cilecca"]
    assert response.status == "match"
    assert response.matched_on == "ai_normalized"
    assert response.matched_text == GRIPPER
    assert [h.base_diagnostic_id for h in response.hypotheses] == [3]


def test_ai_rewrite_without_a_match_still_declares_missing_data(
    db_connection: Connection, matcher: FuzzyMatcher
) -> None:
    ai = StubAIProvider(output="Il motore del nastro produce fumo")

    response = diagnose(db_connection, request("il motore fuma", 1, 1), matcher, ai)

    assert response.status == "no_match"


def test_ai_failure_does_not_block_the_deterministic_answer(db_connection: Connection, matcher: FuzzyMatcher) -> None:
    ai = StubAIProvider(fail=True)

    response = diagnose(db_connection, request("il motore fuma", 1, 1), matcher, ai)

    assert response.status == "no_match"
    assert ai.calls == ["il motore fuma"]
