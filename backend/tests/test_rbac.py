"""Role-based access control on every knowledge base endpoint.

The core rule of the brief: an operator can consult, never write. Export and import
are expert-only too: the CSV is the whole knowledge base, and importing writes to it.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from app.services.csv_service import CSV_COLUMNS

DIAGNOSTIC_BODY = {
    "symptom_description": "L'avvitatore non raggiunge la coppia",
    "affected_component": "Avvitatore elettrico",
    "probable_cause": "Inserto usurato.",
    "recommended_solution": "Sostituire l'inserto.",
}
IMPORT_FILE = ";".join(CSV_COLUMNS) + "\r\n;;;;Sintomo;Componente;Causa;Soluzione"

WRITE_REQUESTS = [
    pytest.param("POST", "/diagnostics", {"json": DIAGNOSTIC_BODY}, 201, id="create"),
    pytest.param("PUT", "/diagnostics/1", {"json": DIAGNOSTIC_BODY}, 200, id="update"),
    pytest.param("DELETE", "/diagnostics/1", {}, 200, id="delete"),
    pytest.param(
        "POST",
        "/diagnostics/import?dry_run=false",
        {"files": {"file": ("kb.csv", IMPORT_FILE.encode(), "text/csv")}},
        200,
        id="import",
    ),
]

EXPERT_ONLY_READS = [
    pytest.param("GET", "/diagnostics/export", id="export"),
    pytest.param("GET", "/diagnostics/import-template", id="template"),
]

READ_REQUESTS = [
    pytest.param("GET", "/families", {}, id="families"),
    pytest.param("GET", "/families/1/phases", {}, id="phases"),
    pytest.param("GET", "/diagnostics", {}, id="list-diagnostics"),
    pytest.param("GET", "/diagnostics/1", {}, id="get-diagnostic"),
    pytest.param(
        "POST",
        "/diagnosis",
        {"json": {"family_id": 1, "messages": [{"role": "operator", "content": "Il nastro trasportatore si ferma a intermittenza"}]}},
        id="diagnosis",
    ),
]


def knowledge_base_snapshot(connection: Connection) -> list[Any]:
    """Returns every row of the knowledge base, to prove nothing changed."""
    return list(connection.execute(text("SELECT * FROM diagnostics ORDER BY id")).all())


# --- Writes ---------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "payload", "expert_status"), WRITE_REQUESTS)
def test_operator_cannot_write_and_nothing_changes(
    client: TestClient,
    operator_headers: dict[str, str],
    db_connection: Connection,
    method: str,
    path: str,
    payload: dict[str, Any],
    expert_status: int,
) -> None:
    before = knowledge_base_snapshot(db_connection)

    response = client.request(method, path, headers=operator_headers, **payload)

    assert response.status_code == 403
    assert knowledge_base_snapshot(db_connection) == before


@pytest.mark.parametrize(("method", "path", "payload", "expert_status"), WRITE_REQUESTS)
def test_anonymous_cannot_write(
    client: TestClient, method: str, path: str, payload: dict[str, Any], expert_status: int
) -> None:
    assert client.request(method, path, **payload).status_code == 401


@pytest.mark.parametrize(("method", "path", "payload", "expert_status"), WRITE_REQUESTS)
def test_expert_can_write(
    client: TestClient,
    expert_headers: dict[str, str],
    method: str,
    path: str,
    payload: dict[str, Any],
    expert_status: int,
) -> None:
    assert client.request(method, path, headers=expert_headers, **payload).status_code == expert_status


# --- Reads ----------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), EXPERT_ONLY_READS)
def test_export_and_template_are_expert_only(
    client: TestClient, expert_headers: dict[str, str], operator_headers: dict[str, str], method: str, path: str
) -> None:
    assert client.request(method, path, headers=operator_headers).status_code == 403
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, headers=expert_headers).status_code == 200


@pytest.mark.parametrize("role_headers", ["operator_headers", "expert_headers"])
@pytest.mark.parametrize(("method", "path", "payload"), READ_REQUESTS)
def test_every_role_can_read(
    client: TestClient,
    request: pytest.FixtureRequest,
    role_headers: str,
    method: str,
    path: str,
    payload: dict[str, Any],
) -> None:
    headers = request.getfixturevalue(role_headers)

    assert client.request(method, path, headers=headers, **payload).status_code == 200


@pytest.mark.parametrize(("method", "path", "payload"), READ_REQUESTS)
def test_anonymous_cannot_read(client: TestClient, method: str, path: str, payload: dict[str, Any]) -> None:
    assert client.request(method, path, **payload).status_code == 401


# --- Role changes take effect immediately ---------------------------------------------


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
