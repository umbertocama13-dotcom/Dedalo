from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import dependencies
from app.services.ai.base import AIProvider

WELDING_CELL = "La cella di saldatura non completa il ciclo ed entra in allarme"
HYPOTHESIS_FIELDS = {
    "diagnostic_id",
    "symptom_description",
    "affected_component",
    "cause",
    "solution",
    "scope",
    "phase_number",
    "phase_name",
    "score",
    "probability",
}


def body(text: str, family_id: int = 3, cycle_phase_id: int | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "cycle_phase_id": cycle_phase_id,
        "messages": [{"role": "operator", "content": text}],
        **extra,
    }


def test_hypotheses_response_contract(client: TestClient, operator_headers: dict[str, str]) -> None:
    response = client.post("/diagnosis", json=body(WELDING_CELL), headers=operator_headers)

    assert response.status_code == 200
    data = response.json()
    assert (data["status"], data["confidence"], data["mode"], data["ai_fallback"]) == ("hypotheses", "high", "deterministic", False)
    assert all(set(hypothesis) == HYPOTHESIS_FIELDS for hypothesis in data["hypotheses"])
    assert sum(hypothesis["probability"] for hypothesis in data["hypotheses"]) + data["unknown_probability"] == 100
    assert data["follow_up"]["type"] == "choice"
    assert data["follow_up"]["options"][0] == {"label": "Nastro trasportatore pallet", "diagnostic_ids": [26]}


def test_excluded_ids_are_honoured(client: TestClient, operator_headers: dict[str, str]) -> None:
    response = client.post("/diagnosis", json=body(WELDING_CELL, excluded_diagnostic_ids=[27, 28]), headers=operator_headers)

    assert response.json()["hypotheses"][0]["diagnostic_id"] == 26
    assert {27, 28}.isdisjoint(h["diagnostic_id"] for h in response.json()["hypotheses"])


def test_no_match_is_a_regular_200_answer(client: TestClient, operator_headers: dict[str, str]) -> None:
    response = client.post("/diagnosis", json=body("il caffè della macchinetta è freddo", family_id=2), headers=operator_headers)

    assert response.status_code == 200
    data = response.json()
    assert (data["status"], data["hypotheses"], data["follow_up"], data["confidence"], data["unknown_probability"]) == (
        "no_match",
        [],
        None,
        None,
        None,
    )
    assert data["message"]


@pytest.mark.parametrize(
    ("family_id", "cycle_phase_id", "expected_status"),
    [(999, None, 404), (1, 999, 404), (1, 7, 400)],
    ids=["unknown-family", "unknown-phase", "phase-of-another-family"],
)
def test_invalid_context(
    client: TestClient, operator_headers: dict[str, str], family_id: int, cycle_phase_id: int | None, expected_status: int
) -> None:
    response = client.post("/diagnosis", json=body("nastro fermo", family_id, cycle_phase_id), headers=operator_headers)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"family_id": 1},
        {"family_id": 1, "messages": []},
        body("   ", family_id=1),
        body("nastro fermo", family_id="uno"),
        body("nastro fermo", family_id=1, cycle_phase_id=0),
        {"family_id": 1, "messages": [{"role": "assistant", "content": "Il nastro è fermo?"}]},
    ],
    ids=["empty", "missing-messages", "no-messages", "blank-message", "non-numeric-family", "zero-phase", "no-operator-message"],
)
def test_invalid_body_is_400_not_422(client: TestClient, operator_headers: dict[str, str], payload: dict[str, Any]) -> None:
    response = client.post("/diagnosis", json=payload, headers=operator_headers)

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], list)


class NarrowingProvider(AIProvider):
    """Stand-in for a model that always keeps only the barrier hypothesis."""

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {"action": "narrow", "diagnostic_ids": [27]}


def test_ai_provider_is_injected_not_hardcoded(app: FastAPI, client: TestClient, operator_headers: dict[str, str]) -> None:
    app.dependency_overrides[dependencies.get_ai_provider] = NarrowingProvider

    data = client.post("/diagnosis", json=body(WELDING_CELL), headers=operator_headers).json()

    assert (data["mode"], [h["diagnostic_id"] for h in data["hypotheses"]]) == ("llm", [27])
