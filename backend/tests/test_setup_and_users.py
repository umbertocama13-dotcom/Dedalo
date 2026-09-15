"""First-start setup and user management, on MySQL and SQLite.

The seeded test database already has two users, so "empty installation" tests delete
users and diagnostics inside the test transaction, which is rolled back afterwards.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from app.config import Settings
from app.repositories import diagnostics_repository
from app.schemas.users import SetupIn, UserIn
from app.services import setup_service, user_service
from app.services.csv_service import parse_diagnostics_csv

NEW_EXPERT = {"username": "mario.rossi", "password": "password-sicura", "load_sample_diagnostics": True}


@pytest.fixture
def empty_installation(db_connection: Connection) -> Connection:
    """The test database as a fresh desktop install: catalog only, no users, no diagnostics."""
    db_connection.execute(text("DELETE FROM diagnostics"))
    db_connection.execute(text("DELETE FROM users"))
    return db_connection


def sample_csv(settings: Settings) -> Path:
    return Path(settings.sample_diagnostics_csv)


def assert_http_error(call: Any, expected_status: int) -> None:
    with pytest.raises(HTTPException) as error:
        call()
    assert error.value.status_code == expected_status


# --- Sample data ------------------------------------------------------------------------


def test_sample_csv_matches_the_seed(db_connection: Connection, settings: Settings) -> None:
    parsed = parse_diagnostics_csv(sample_csv(settings).read_bytes())
    seeded = diagnostics_repository.list_diagnostics(db_connection)

    assert parsed.errors == []
    assert [
        (row.symptom_description, row.affected_component, row.probable_cause, row.recommended_solution, row.family_name, row.phase_number)
        for row in parsed.rows
    ] == [
        (row["symptom_description"], row["affected_component"], row["probable_cause"], row["recommended_solution"], row["family_name"], row["phase_number"])
        for row in seeded
    ]
    assert all(row.id is None for row in parsed.rows)


# --- Setup service ----------------------------------------------------------------------


def test_seeded_database_needs_no_setup_and_refuses_it(db_connection: Connection, settings: Settings) -> None:
    assert setup_service.needs_setup(db_connection) is False
    assert_http_error(lambda: setup_service.create_first_expert(db_connection, SetupIn(**NEW_EXPERT), sample_csv(settings)), 409)


def test_first_expert_with_sample_diagnostics(empty_installation: Connection, settings: Settings) -> None:
    assert setup_service.needs_setup(empty_installation) is True

    result = setup_service.create_first_expert(empty_installation, SetupIn(**NEW_EXPERT), sample_csv(settings))

    assert (result.user.username, result.user.role, result.sample_diagnostics_loaded) == ("mario.rossi", "expert", 36)
    assert setup_service.needs_setup(empty_installation) is False
    authors = {row["created_by"] for row in diagnostics_repository.list_diagnostics(empty_installation)}
    assert authors == {result.user.id}
    # The endpoint works only once.
    assert_http_error(
        lambda: setup_service.create_first_expert(empty_installation, SetupIn(**{**NEW_EXPERT, "username": "altro"}), sample_csv(settings)),
        409,
    )


def test_first_expert_without_sample_diagnostics(empty_installation: Connection) -> None:
    result = setup_service.create_first_expert(
        empty_installation, SetupIn(**{**NEW_EXPERT, "load_sample_diagnostics": False}), sample_csv=None
    )

    assert result.sample_diagnostics_loaded == 0
    assert diagnostics_repository.list_diagnostics(empty_installation) == []


def test_missing_sample_file_is_rejected_before_creating_the_user(empty_installation: Connection, tmp_path: Path) -> None:
    assert_http_error(
        lambda: setup_service.create_first_expert(empty_installation, SetupIn(**NEW_EXPERT), tmp_path / "missing.csv"), 400
    )
    assert setup_service.needs_setup(empty_installation) is True


# --- User service -----------------------------------------------------------------------


def test_lists_users_without_hashes(db_connection: Connection) -> None:
    users = user_service.list_users(db_connection)

    assert [(user.username, user.role) for user in users] == [("expert_demo", "expert"), ("operator_demo", "operator")]


def test_created_user_can_log_in(db_connection: Connection, settings: Settings) -> None:
    from app.services.auth_service import authenticate_user

    created = user_service.create_user(db_connection, UserIn(username="luca", password="turno-di-notte", role="operator"))

    assert created.role == "operator"
    assert authenticate_user(db_connection, "luca", "turno-di-notte", settings)


@pytest.mark.parametrize("username", ["operator_demo", "OPERATOR_DEMO"], ids=["same-case", "different-case"])
def test_duplicate_username_is_409(db_connection: Connection, username: str) -> None:
    assert_http_error(
        lambda: user_service.create_user(db_connection, UserIn(username=username, password="password-sicura", role="operator")),
        409,
    )


def test_password_over_bcrypt_limit_is_400(db_connection: Connection) -> None:
    # 30 characters but 90 bytes in UTF-8.
    assert_http_error(
        lambda: user_service.create_user(db_connection, UserIn(username="luca", password="€" * 30, role="operator")), 400
    )


# --- Routes -----------------------------------------------------------------------------


def test_setup_status_is_public(client: TestClient) -> None:
    assert client.get("/setup/status").json() == {"needs_setup": False}


def test_setup_then_login_through_the_api(client: TestClient, empty_installation: Connection) -> None:
    assert client.get("/setup/status").json() == {"needs_setup": True}

    created = client.post("/setup", json=NEW_EXPERT)
    assert (created.status_code, created.json()["sample_diagnostics_loaded"]) == (201, 36)

    token = client.post("/auth/login", data={"username": "mario.rossi", "password": "password-sicura"}).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["role"] == "expert"
    assert client.post("/setup", json=NEW_EXPERT).status_code == 409


def test_setup_on_an_installed_app_is_409(client: TestClient) -> None:
    assert client.post("/setup", json=NEW_EXPERT).status_code == 409


def test_expert_manages_users(client: TestClient, expert_headers: dict[str, str]) -> None:
    created = client.post("/users", json={"username": "luca", "password": "turno-di-notte", "role": "operator"}, headers=expert_headers)

    assert (created.status_code, created.json()["role"]) == (201, "operator")
    assert "password_hash" not in created.json()
    assert "luca" in [user["username"] for user in client.get("/users", headers=expert_headers).json()]


@pytest.mark.parametrize(
    ("method", "payload"),
    [("GET", None), ("POST", {"username": "luca", "password": "turno-di-notte", "role": "expert"})],
    ids=["list", "create"],
)
def test_only_experts_manage_users(
    client: TestClient, operator_headers: dict[str, str], db_connection: Connection, method: str, payload: dict[str, Any] | None
) -> None:
    before = db_connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()

    assert client.request(method, "/users", json=payload, headers=operator_headers).status_code == 403
    assert client.request(method, "/users", json=payload).status_code == 401
    assert db_connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == before


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "lu", "password": "turno-di-notte", "role": "operator"},
        {"username": "luca rossi", "password": "turno-di-notte", "role": "operator"},
        {"username": "luca", "password": "corta", "role": "operator"},
        {"username": "luca", "password": "turno-di-notte", "role": "admin"},
    ],
    ids=["username-too-short", "username-with-space", "password-too-short", "unknown-role"],
)
def test_invalid_user_bodies_are_400(client: TestClient, expert_headers: dict[str, str], payload: dict[str, Any]) -> None:
    assert client.post("/users", json=payload, headers=expert_headers).status_code == 400
