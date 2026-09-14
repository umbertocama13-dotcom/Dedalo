from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import dependencies
from app.services.ai.base import AIProvider

HYPOTHESIS_FIELDS = {
    "base_diagnostic_id",
    "exception_id",
    "symptom_description",
    "affected_component",
    "cause",
    "solution",
    "source",
    "score",
}


def test_match_response_contract(client: TestClient, operator_headers: dict[str, str]) -> None:
    response = client.post(
        "/diagnosis",
        json={"symptom": "nastro trasportatre si ferma a intermitenza", "family_id": 2, "cycle_phase_id": 5},
        headers=operator_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["matched_on"]) == ("match", "original")
    assert all(set(hypothesis) == HYPOTHESIS_FIELDS for hypothesis in body["hypotheses"])
    assert [(h["base_diagnostic_id"], h["source"], h["exception_id"]) for h in body["hypotheses"]] == [
        (1, "base", None),
        (2, "exception", 3),
    ]


def test_no_match_is_a_regular_200_answer(client: TestClient, operator_headers: dict[str, str]) -> None:
    response = client.post(
        "/diagnosis", json={"symptom": "Il motore fa fumo", "family_id": 1, "cycle_phase_id": 1}, headers=operator_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["hypotheses"], body["matched_on"]) == ("no_match", [], None)
    assert body["message"]


@pytest.mark.parametrize(
    ("family_id", "cycle_phase_id", "expected_status"),
    [(999, 1, 404), (1, 999, 404), (1, 7, 400)],
    ids=["unknown-family", "unknown-phase", "phase-of-another-family"],
)
def test_invalid_context(
    client: TestClient, operator_headers: dict[str, str], family_id: int, cycle_phase_id: int, expected_status: int
) -> None:
    response = client.post(
        "/diagnosis",
        json={"symptom": "nastro fermo", "family_id": family_id, "cycle_phase_id": cycle_phase_id},
        headers=operator_headers,
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"symptom": "   ", "family_id": 1, "cycle_phase_id": 1},
        {"symptom": "nastro fermo", "family_id": "uno", "cycle_phase_id": 1},
        {"symptom": "nastro fermo", "family_id": 1},
        {"symptom": "x" * 501, "family_id": 1, "cycle_phase_id": 1},
    ],
    ids=["empty", "blank-symptom", "non-numeric-family", "missing-phase", "symptom-too-long"],
)
def test_invalid_body_is_400_not_422(client: TestClient, operator_headers: dict[str, str], body: dict[str, Any]) -> None:
    response = client.post("/diagnosis", json=body, headers=operator_headers)

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], list)


class FixedAnswerAIProvider(AIProvider):
    """Stand-in for an external model that always rewrites the text the same way."""

    def normalize_symptom(self, text: str) -> str:
        return "La pinza del robot non chiude completamente"


def test_ai_provider_is_injected_not_hardcoded(
    app: FastAPI, client: TestClient, operator_headers: dict[str, str]
) -> None:
    app.dependency_overrides[dependencies.get_ai_provider] = FixedAnswerAIProvider

    response = client.post(
        "/diagnosis",
        json={"symptom": "boh la pinza fa cilecca", "family_id": 1, "cycle_phase_id": 3},
        headers=operator_headers,
    )

    body = response.json()
    assert (body["status"], body["matched_on"]) == ("match", "ai_normalized")
    assert [h["base_diagnostic_id"] for h in body["hypotheses"]] == [3]
