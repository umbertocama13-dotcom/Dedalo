from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from app.services.csv_service import CSV_COLUMNS

NEW_DIAGNOSTIC = {
    "symptom_description": "L'ugello della torcia si intasa di spruzzi",
    "affected_component": "Ugello torcia",
    "probable_cause": "Liquido antispruzzo esaurito.",
    "recommended_solution": "Pulire l'ugello e ricaricare il liquido antispruzzo.",
}
CSV_HEADER = ";".join(CSV_COLUMNS)


def count_diagnostics(connection: Connection) -> int:
    return connection.execute(text("SELECT COUNT(*) FROM diagnostics")).scalar_one()


def csv_upload(*lines: str) -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("kb.csv", "\r\n".join((CSV_HEADER, *lines)).encode("utf-8"), "text/csv")}


# --- CRUD -----------------------------------------------------------------------------


def test_expert_adds_a_phase_diagnostic_and_the_operator_finds_it(
    client: TestClient, expert_headers: dict[str, str], operator_headers: dict[str, str]
) -> None:
    created = client.post("/diagnostics", json={**NEW_DIAGNOSTIC, "family_id": 3, "cycle_phase_id": 11}, headers=expert_headers)

    assert created.status_code == 201
    body = created.json()
    assert (body["created_by"], body["family_name"], body["phase_name"]) == (1, "Cella di saldatura robotizzata", "Saldatura")

    diagnosis = client.post(
        "/diagnosis",
        json={
            "family_id": 3,
            "cycle_phase_id": 11,
            "messages": [{"role": "operator", "content": NEW_DIAGNOSTIC["symptom_description"]}],
        },
        headers=operator_headers,
    ).json()
    first = diagnosis["hypotheses"][0]
    assert (first["diagnostic_id"], first["scope"]) == (body["id"], "phase")


def test_update_and_delete_a_diagnostic(client: TestClient, expert_headers: dict[str, str]) -> None:
    updated = client.put("/diagnostics/1", json={**NEW_DIAGNOSTIC, "family_id": 2}, headers=expert_headers)
    assert (updated.status_code, updated.json()["family_name"]) == (200, "Confezionatrice flow-pack")

    deleted = client.delete("/diagnostics/1", headers=expert_headers)
    assert (deleted.status_code, deleted.json()) == (200, {"message": "Diagnostic deleted"})

    assert client.get("/diagnostics/1", headers=expert_headers).status_code == 404
    assert client.delete("/diagnostics/1", headers=expert_headers).status_code == 404


def test_list_filters_are_query_parameters(client: TestClient, operator_headers: dict[str, str]) -> None:
    response = client.get("/diagnostics", params={"family_id": 3, "cycle_phase_id": 10}, headers=operator_headers)

    assert [d["id"] for d in response.json()] == [34, 35]
    assert client.get("/diagnostics", params={"family_id": 0}, headers=operator_headers).status_code == 400


@pytest.mark.parametrize(
    ("method", "path", "body", "expected_status"),
    [
        ("POST", "/diagnostics", {**NEW_DIAGNOSTIC, "symptom_description": "  "}, 400),
        ("POST", "/diagnostics", {k: v for k, v in NEW_DIAGNOSTIC.items() if k != "probable_cause"}, 400),
        ("POST", "/diagnostics", {**NEW_DIAGNOSTIC, "affected_component": "x" * 151}, 400),
        ("POST", "/diagnostics", {**NEW_DIAGNOSTIC, "cycle_phase_id": 11}, 400),
        ("POST", "/diagnostics", {**NEW_DIAGNOSTIC, "family_id": 1, "cycle_phase_id": 7}, 400),
        ("POST", "/diagnostics", {**NEW_DIAGNOSTIC, "family_id": 999}, 404),
        ("PUT", "/diagnostics/999", NEW_DIAGNOSTIC, 404),
    ],
    ids=["blank-symptom", "missing-cause", "component-too-long", "phase-without-family", "phase-of-another-family", "unknown-family", "unknown-diagnostic"],
)
def test_write_errors(
    client: TestClient, expert_headers: dict[str, str], method: str, path: str, body: dict[str, Any], expected_status: int
) -> None:
    assert client.request(method, path, json=body, headers=expert_headers).status_code == expected_status


# --- CSV ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "filename"),
    [("/diagnostics/export", "dedalo_diagnostics.csv"), ("/diagnostics/import-template", "dedalo_template.csv")],
)
def test_csv_downloads(client: TestClient, expert_headers: dict[str, str], path: str, filename: str) -> None:
    response = client.get(path, headers=expert_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'
    assert response.content.startswith(b"\xef\xbb\xbf" + CSV_HEADER.encode())


def test_import_is_a_dry_run_by_default(client: TestClient, expert_headers: dict[str, str], db_connection: Connection) -> None:
    response = client.post("/diagnostics/import", files=csv_upload(";;;;Sintomo nuovo;Componente;Causa;Soluzione"), headers=expert_headers)

    assert response.status_code == 200
    assert (response.json()["applied"], response.json()["to_create"]) == (False, 1)
    assert count_diagnostics(db_connection) == 36


def test_import_applies_when_asked(client: TestClient, expert_headers: dict[str, str], db_connection: Connection) -> None:
    response = client.post(
        "/diagnostics/import",
        params={"dry_run": "false"},
        files=csv_upload(";;;;Sintomo nuovo;Componente;Causa;Soluzione"),
        headers=expert_headers,
    )

    assert (response.status_code, response.json()["applied"]) == (200, True)
    assert count_diagnostics(db_connection) == 37


def test_import_with_errors_is_400_with_the_report(
    client: TestClient, expert_headers: dict[str, str], db_connection: Connection
) -> None:
    response = client.post(
        "/diagnostics/import",
        params={"dry_run": "false"},
        files=csv_upload(";;;;Sintomo nuovo;Componente;Causa;Soluzione", ";Cella inventata;;;S;C;P;R"),
        headers=expert_headers,
    )

    assert response.status_code == 400
    [error] = response.json()["detail"]["errors"]
    assert (error["line"], error["column"]) == (3, "family_name")
    assert count_diagnostics(db_connection) == 36


def test_import_without_file_is_400(client: TestClient, expert_headers: dict[str, str]) -> None:
    assert client.post("/diagnostics/import", headers=expert_headers).status_code == 400
