from typing import Any

import pytest
from fastapi.testclient import TestClient

NEW_DIAGNOSTIC = {
    "symptom_description": "Il robot emette un allarme di collisione",
    "affected_component": "Robot antropomorfo",
    "probable_cause": "Zona di lavoro ingombra.",
    "recommended_solution": "Liberare la zona e ripristinare l'allarme.",
}
EXCEPTION_BODY = {"family_id": 1, "cycle_phase_id": 1, "specific_cause": "Causa.", "specific_solution": "Soluzione."}


def test_expert_adds_a_diagnostic_and_the_operator_finds_it(
    client: TestClient, expert_headers: dict[str, str], operator_headers: dict[str, str]
) -> None:
    created = client.post("/diagnostics", json=NEW_DIAGNOSTIC, headers=expert_headers)

    assert created.status_code == 201
    assert created.json()["created_by"] == 1

    diagnosis = client.post(
        "/diagnosis",
        json={"symptom": "il robot emette allarme di collisione", "family_id": 1, "cycle_phase_id": 3},
        headers=operator_headers,
    )
    assert [h["base_diagnostic_id"] for h in diagnosis.json()["hypotheses"]] == [created.json()["id"]]


def test_update_and_delete_a_diagnostic(client: TestClient, expert_headers: dict[str, str]) -> None:
    updated = client.put("/diagnostics/1", json=NEW_DIAGNOSTIC, headers=expert_headers)
    assert (updated.status_code, updated.json()["affected_component"]) == (200, "Robot antropomorfo")

    deleted = client.delete("/diagnostics/1", headers=expert_headers)
    assert (deleted.status_code, deleted.json()) == (200, {"message": "Diagnostic deleted"})

    assert client.get("/diagnostics/1", headers=expert_headers).status_code == 404
    assert client.delete("/diagnostics/1", headers=expert_headers).status_code == 404


def test_update_of_unknown_diagnostic_is_404(client: TestClient, expert_headers: dict[str, str]) -> None:
    assert client.put("/diagnostics/999", json=NEW_DIAGNOSTIC, headers=expert_headers).status_code == 404


def test_exception_lifecycle(client: TestClient, expert_headers: dict[str, str]) -> None:
    created = client.post("/diagnostics/1/exceptions", json=EXCEPTION_BODY, headers=expert_headers)
    assert created.status_code == 201
    exception_id = created.json()["id"]

    listed = client.get("/diagnostics/1/exceptions", headers=expert_headers).json()
    assert [e["id"] for e in listed] == [exception_id]

    moved = client.put(
        f"/diagnostics/1/exceptions/{exception_id}", json={**EXCEPTION_BODY, "cycle_phase_id": 3}, headers=expert_headers
    )
    assert (moved.status_code, moved.json()["cycle_phase_id"]) == (200, 3)

    assert client.delete(f"/diagnostics/1/exceptions/{exception_id}", headers=expert_headers).status_code == 200
    assert client.get("/diagnostics/1/exceptions", headers=expert_headers).json() == []


@pytest.mark.parametrize(
    ("method", "path", "body", "expected_status"),
    [
        ("POST", "/diagnostics/3/exceptions", {**EXCEPTION_BODY, "cycle_phase_id": 2}, 409),
        ("POST", "/diagnostics/1/exceptions", {**EXCEPTION_BODY, "cycle_phase_id": 7}, 400),
        ("POST", "/diagnostics/999/exceptions", EXCEPTION_BODY, 404),
        ("PUT", "/diagnostics/2/exceptions/1", EXCEPTION_BODY, 404),
        ("DELETE", "/diagnostics/4/exceptions/1", None, 404),
    ],
    ids=["duplicate-context", "phase-of-another-family", "unknown-diagnostic", "update-wrong-owner", "delete-wrong-owner"],
)
def test_exception_errors(
    client: TestClient,
    expert_headers: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any] | None,
    expected_status: int,
) -> None:
    assert client.request(method, path, json=body, headers=expert_headers).status_code == expected_status


@pytest.mark.parametrize(
    "body",
    [
        {**NEW_DIAGNOSTIC, "symptom_description": "  "},
        {key: value for key, value in NEW_DIAGNOSTIC.items() if key != "probable_cause"},
        {**NEW_DIAGNOSTIC, "affected_component": "x" * 151},
    ],
    ids=["blank-symptom", "missing-cause", "component-too-long"],
)
def test_invalid_diagnostic_body_is_400(
    client: TestClient, expert_headers: dict[str, str], body: dict[str, Any]
) -> None:
    assert client.post("/diagnostics", json=body, headers=expert_headers).status_code == 400
