"""Integration tests for the diagnosis conversation on the seeded test database.

The matcher is the real SemanticMatcher with the fake bag-of-words embedder: scores
depend only on shared words, which keeps the known cases below stable. Seed facts:
- 26, 27, 28: same symptom of family 3 ("the welding cell does not complete the cycle")
  with three different components;
- 1, 2: generic conveyor symptom with the same component; 22 is the same symptom for
  family 2 / phase 5 with another component;
- 11, 16: "the gripper does not close completely" (16 only in family 1 / phase 2).
"""

import json
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection

from app.config import Settings
from app.repositories import diagnostics_repository
from app.schemas.diagnosis import DiagnosisRequest, DiagnosisResponse
from app.services.ai.base import AIProvider, AIProviderError
from app.services.ai.noop_provider import NoopAIProvider
from app.services.diagnosis_service import diagnose
from app.services.embeddings.embedding_cache import EmbeddingCache
from app.services.matching.semantic_matcher import SemanticMatcher
from tests.fake_embedder import FakeEmbedder

WELDING_CELL = "La cella di saldatura non completa il ciclo ed entra in allarme"
CONVEYOR = "Il nastro trasportatore si ferma a intermittenza"


class ScriptedProvider(AIProvider):
    """Stand-in for the model: returns a fixed answer or fails, and records every prompt."""

    def __init__(self, answer: dict[str, Any] | None = None, fail: bool = False) -> None:
        self.answer = answer or {}
        self.fail = fail
        self.payloads: list[dict[str, Any]] = []

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        self.payloads.append(json.loads(messages[1]["content"]))
        if self.fail:
            raise AIProviderError("model unavailable")
        return self.answer


@pytest.fixture
def matcher(settings: Settings) -> SemanticMatcher:
    return SemanticMatcher(
        EmbeddingCache(FakeEmbedder()),
        threshold=settings.semantic_recall_threshold,
        max_results=settings.max_candidates,
        use_fuzzy=True,
    )


def ask(
    connection: Connection,
    matcher: SemanticMatcher,
    settings: Settings,
    *texts: str,
    family_id: int = 3,
    cycle_phase_id: int | None = None,
    excluded: list[int] | None = None,
    provider: AIProvider | None = None,
) -> DiagnosisResponse:
    """Sends a conversation made of operator messages, with assistant questions given as "?..." texts."""
    messages = [
        {"role": "assistant", "content": text[1:]} if text.startswith("?") else {"role": "operator", "content": text}
        for text in texts
    ]
    request = DiagnosisRequest(
        family_id=family_id, cycle_phase_id=cycle_phase_id, messages=messages, excluded_diagnostic_ids=excluded or []
    )
    return diagnose(connection, request, matcher, provider or NoopAIProvider(), settings)


def ids(response: DiagnosisResponse) -> list[int]:
    return [hypothesis.diagnostic_id for hypothesis in response.hypotheses]


def option_ids(response: DiagnosisResponse) -> list[list[int]]:
    assert response.follow_up is not None and response.follow_up.type == "choice"
    return [option.diagnostic_ids for option in response.follow_up.options]


# --- Deterministic flow ----------------------------------------------------------------


def test_whole_cell_stop_lists_every_cause_and_asks_which_component(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    response = ask(db_connection, matcher, settings, WELDING_CELL)

    assert (response.status, response.confidence, response.mode, response.ai_fallback) == ("hypotheses", "high", "deterministic", False)
    assert ids(response)[:3] == [26, 27, 28]
    assert [h.probability for h in response.hypotheses][:3] == [34, 33, 33]
    assert response.unknown_probability == 0
    assert sum(h.probability for h in response.hypotheses) + response.unknown_probability == 100
    assert [option.label for option in response.follow_up.options] == [
        "Nastro trasportatore pallet",
        "Barriera fotoelettrica di sicurezza",
        "Torcia di saldatura",
    ]
    assert response.hypotheses[0].cause.startswith("Il nastro trasportatore pallet è guasto")


def test_choosing_an_option_is_excluding_the_others(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    first = ask(db_connection, matcher, settings, CONVEYOR, family_id=2, cycle_phase_id=5)
    assert option_ids(first) == [[22], [1, 2]]

    # The operator picks "Svolgitore bobina": the client excludes the ids of the other option.
    chosen = ask(db_connection, matcher, settings, CONVEYOR, family_id=2, cycle_phase_id=5, excluded=[1, 2])

    assert ids(chosen) == [22]
    assert (chosen.hypotheses[0].probability, chosen.hypotheses[0].scope, chosen.follow_up) == (100, "phase", None)


def test_none_of_these_leaves_only_uncertain_hypotheses(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    response = ask(db_connection, matcher, settings, WELDING_CELL, excluded=[26, 27, 28])

    assert response.status == "hypotheses"
    assert response.confidence == "low"
    assert all(h.score < settings.semantic_match_threshold for h in response.hypotheses)
    # Weak hypotheses must not look likely: most of the probability goes to "none of these".
    assert response.unknown_probability > 50
    assert sum(h.probability for h in response.hypotheses) + response.unknown_probability == 100
    assert response.follow_up is not None and response.follow_up.type == "choice"


def test_same_symptom_and_component_need_no_question(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    response = ask(db_connection, matcher, settings, CONVEYOR, family_id=1)

    assert ids(response) == [1, 2]
    assert [h.probability for h in response.hypotheses] == [50, 50]
    assert response.follow_up is None


def test_rows_of_other_phases_are_not_candidates(db_connection: Connection, matcher: SemanticMatcher, settings: Settings) -> None:
    assert ids(ask(db_connection, matcher, settings, CONVEYOR, family_id=2, cycle_phase_id=6)) == [1, 2]


def test_opposite_symptom_is_never_proposed(db_connection: Connection, matcher: SemanticMatcher, settings: Settings) -> None:
    response = ask(db_connection, matcher, settings, "La pinza del robot chiude completamente", family_id=1, cycle_phase_id=2)

    assert not {11, 16} & set(ids(response))


def test_later_answers_keep_the_first_description_relevant(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    response = ask(db_connection, matcher, settings, WELDING_CELL, "?Il nastro pallet è fermo?", "sì")

    assert ids(response)[:3] == [26, 27, 28]


def test_unknown_symptom_declares_missing_data(db_connection: Connection, matcher: SemanticMatcher, settings: Settings) -> None:
    response = ask(db_connection, matcher, settings, "il caffè della macchinetta è freddo", family_id=2)

    assert (response.status, response.mode, response.hypotheses, response.follow_up) == ("no_match", "deterministic", [], None)
    assert response.message


def test_knowledge_base_changes_are_visible_immediately(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    new_id = diagnostics_repository.insert_diagnostic(
        db_connection, "Il robot emette un allarme di sovraccarico", "Robot", "Causa", "Soluzione", 1, None, 1
    )

    response = ask(db_connection, matcher, settings, "il robot emette un allarme di sovraccarico", family_id=1)

    assert ids(response)[0] == new_id


@pytest.mark.parametrize(
    ("family_id", "cycle_phase_id", "expected_status"),
    [(999, None, 404), (1, 999, 404), (1, 7, 400)],
    ids=["unknown-family", "unknown-phase", "phase-of-another-family"],
)
def test_invalid_context_is_rejected(
    db_connection: Connection,
    matcher: SemanticMatcher,
    settings: Settings,
    family_id: int,
    cycle_phase_id: int | None,
    expected_status: int,
) -> None:
    with pytest.raises(HTTPException) as error:
        ask(db_connection, matcher, settings, CONVEYOR, family_id=family_id, cycle_phase_id=cycle_phase_id)

    assert error.value.status_code == expected_status


# --- LLM flow --------------------------------------------------------------------------


def test_model_question_comes_with_the_hypotheses(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    provider = ScriptedProvider({"action": "ask", "question": "Il nastro pallet è fermo?"})

    response = ask(db_connection, matcher, settings, WELDING_CELL, provider=provider)

    assert (response.mode, response.follow_up.type, response.follow_up.question) == ("llm", "question", "Il nastro pallet è fermo?")
    assert ids(response)[:3] == [26, 27, 28]
    [payload] = provider.payloads
    assert payload["context"] == "Cella di saldatura robotizzata, fase non indicata"
    assert payload["questions_left"] == 3
    assert [candidate["id"] for candidate in payload["candidates"]] == ids(response)


def test_model_narrowing_keeps_only_the_chosen_hypotheses(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings
) -> None:
    provider = ScriptedProvider({"action": "narrow", "diagnostic_ids": [27]})

    response = ask(db_connection, matcher, settings, WELDING_CELL, "?Il nastro pallet è fermo?", "no, gira", provider=provider)

    assert (response.mode, ids(response), response.hypotheses[0].probability, response.follow_up) == ("llm", [27], 100, None)
    assert provider.payloads[0]["questions_left"] == 2


def test_model_can_declare_missing_data(db_connection: Connection, matcher: SemanticMatcher, settings: Settings) -> None:
    response = ask(db_connection, matcher, settings, WELDING_CELL, provider=ScriptedProvider({"action": "no_match"}))

    assert (response.status, response.mode, response.hypotheses) == ("no_match", "llm", [])


@pytest.mark.parametrize(
    "provider",
    [ScriptedProvider({"action": "narrow", "diagnostic_ids": [999]}), ScriptedProvider(fail=True)],
    ids=["invented-id", "provider-down"],
)
def test_invalid_or_missing_model_answers_fall_back_to_the_deterministic_flow(
    db_connection: Connection, matcher: SemanticMatcher, settings: Settings, provider: ScriptedProvider
) -> None:
    response = ask(db_connection, matcher, settings, WELDING_CELL, provider=provider)

    assert (response.mode, response.ai_fallback) == ("deterministic", True)
    assert option_ids(response) == [[26], [27], [28]]


def test_no_questions_left_after_the_limit(db_connection: Connection, matcher: SemanticMatcher, settings: Settings) -> None:
    provider = ScriptedProvider({"action": "ask", "question": "Ancora una domanda?"})

    response = ask(db_connection, matcher, settings, WELDING_CELL, "?D1", "r1", "?D2", "r2", "?D3", "r3", provider=provider)

    assert provider.payloads[0]["questions_left"] == 0
    # Asking anyway is an invalid answer: the deterministic choice takes over.
    assert (response.mode, response.follow_up.type) == ("deterministic", "choice")


def test_model_is_not_called_without_candidates(db_connection: Connection, matcher: SemanticMatcher, settings: Settings) -> None:
    provider = ScriptedProvider({"action": "narrow", "diagnostic_ids": [1]})

    response = ask(db_connection, matcher, settings, "il caffè della macchinetta è freddo", family_id=2, provider=provider)

    assert (response.status, provider.payloads) == ("no_match", [])


def test_context_label_names_the_phase(db_connection: Connection, matcher: SemanticMatcher, settings: Settings) -> None:
    provider = ScriptedProvider({"action": "no_match"})

    ask(db_connection, matcher, settings, CONVEYOR, family_id=2, cycle_phase_id=5, provider=provider)

    assert provider.payloads[0]["context"] == "Confezionatrice flow-pack, fase 1 Svolgimento film"
