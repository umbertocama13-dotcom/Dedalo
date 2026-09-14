"""Role-based access control on every knowledge base endpoint.

The core rule of the brief: an operator can consult, never write.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

DIAGNOSTIC_BODY = {
    "symptom_description": "L'avvitatore non raggiunge la coppia",
    "affected_component": "Avvitatore elettrico",
    "probable_cause": "Inserto usurato.",
    "recommended_solution": "Sostituire l'inserto.",
}
EXCEPTION_BODY = {"family_id": 1, "cycle_phase_id": 1, "specific_cause": "Causa.", "specific_solution": "Soluzione."}

WRITE_REQUESTS = [
    pytest.param("POST", "/diagnostics", DIAGNOSTIC_BODY, 201, id="create-diagnostic"),
    pytest.param("PUT", "/diagnostics/1", DIAGNOSTIC_BODY, 200, id="update-diagnostic"),
    pytest.param("DELETE", "/diagnostics/1", None, 200, id="delete-diagnostic"),
    pytest.param("POST", "/diagnostics/3/exceptions", EXCEPTION_BODY, 201, id="create-exception"),
    pytest.param("PUT", "/diagnostics/3/exceptions/1", EXCEPTION_BODY, 200, id="update-exception"),
    pytest.param("DELETE", "/diagnostics/3/exceptions/1", None, 200, id="delete-exception"),
]

READ_REQUESTS = [
    pytest.param("GET", "/families", None, id="families"),
    pytest.param("GET", "/families/1/phases", None, id="phases"),
    pytest.param("GET", "/diagnostics", None, id="list-diagnostics"),
    pytest.param("GET", "/diagnostics/1", None, id="get-diagnostic"),
    pytest.param("GET", "/diagnostics/3/exceptions", None, id="list-exceptions"),
    pytest.param(
        "POST",
        "/diagnosis",
        {"symptom": "Il nastro trasportatore si ferma a intermittenza", "family_id": 1, "cycle_phase_id": 1},
        id="diagnosis",
    ),
]


def knowledge_base_snapshot(connection: Connection) -> tuple[list[Any], list[Any]]:
    """Returns every row of the knowledge base tables, to prove nothing changed."""
    diagnostics = connection.execute(text("SELECT * FROM base_diagnostics ORDER BY id")).all()
    exceptions = connection.execute(text("SELECT * FROM diagnostic_exceptions ORDER BY id")).all()
    return list(diagnostics), list(exceptions)


# --- Writes ---------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body", "expert_status"), WRITE_REQUESTS)
def test_operator_cannot_write_and_nothing_changes(
    client: TestClient,
    operator_headers: dict[str, str],
    db_connection: Connection,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    expert_status: int,
) -> None:
    before = knowledge_base_snapshot(db_connection)

    response = client.request(method, path, json=body, headers=operator_headers)

    assert response.status_code == 403
    assert knowledge_base_snapshot(db_connection) == before


@pytest.mark.parametrize(("method", "path", "body", "expert_status"), WRITE_REQUESTS)
def test_anonymous_cannot_write(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None, expert_status: int
) -> None:
    assert client.request(method, path, json=body).status_code == 401


@pytest.mark.parametrize(("method", "path", "body", "expert_status"), WRITE_REQUESTS)
def test_expert_can_write(
    client: TestClient,
    expert_headers: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any] | None,
    expert_status: int,
) -> None:
    assert client.request(method, path, json=body, headers=expert_headers).status_code == expert_status


# --- Reads ----------------------------------------------------------------------


@pytest.mark.parametrize("role_headers", ["operator_headers", "expert_headers"])
@pytest.mark.parametrize(("method", "path", "body"), READ_REQUESTS)
def test_every_role_can_read(
    client: TestClient,
    request: pytest.FixtureRequest,
    role_headers: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    headers = request.getfixturevalue(role_headers)

    assert client.request(method, path, json=body, headers=headers).status_code == 200


@pytest.mark.parametrize(("method", "path", "body"), READ_REQUESTS)
def test_anonymous_cannot_read(client: TestClient, method: str, path: str, body: dict[str, Any] | None) -> None:
    assert client.request(method, path, json=body).status_code == 401


# --- Role changes take effect immediately ----------------------------------------


def test_promoted_operator_can_write_with_the_same_token(
    client: TestClient, operator_headers: dict[str, str], db_connection: Connection
) -> None:
    assert client.post("/diagnostics", json=DIAGNOSTIC_BODY, headers=operator_headers).status_code == 403

    db_connection.execute(text("UPDATE users SET role = 'expert' WHERE id = 2"))

    assert client.post("/diagnostics", json=DIAGNOSTIC_BODY, headers=operator_headers).status_code == 201


def test_demoted_expert_loses_write_access_with_the_same_token(
    client: TestClient, expert_headers: dict[str, str], db_connection: Connection
) -> None:
    db_connection.execute(text("UPDATE users SET role = 'operator' WHERE id = 1"))

    assert client.post("/diagnostics", json=DIAGNOSTIC_BODY, headers=expert_headers).status_code == 403
