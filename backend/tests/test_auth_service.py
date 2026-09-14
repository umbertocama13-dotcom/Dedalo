"""Integration tests for authentication against the seeded test database."""

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection, text

from app.config import Settings
from app.services.auth_service import authenticate_user, get_user_from_token
from app.services.security import create_access_token, decode_access_token


def test_valid_credentials_return_a_token_for_that_user(db_connection: Connection, settings: Settings) -> None:
    token = authenticate_user(db_connection, "operator_demo", "operator123", settings)

    payload = decode_access_token(token, settings)
    assert (payload.user_id, payload.role) == (2, "operator")


@pytest.mark.parametrize(
    ("username", "password"),
    [("operator_demo", "wrong"), ("nobody", "operator123")],
    ids=["wrong-password", "unknown-user"],
)
def test_invalid_credentials_get_the_same_400(
    db_connection: Connection, settings: Settings, username: str, password: str
) -> None:
    with pytest.raises(HTTPException) as error:
        authenticate_user(db_connection, username, password, settings)

    # Same status and message in both cases: the response must not reveal which usernames exist.
    assert error.value.status_code == 400
    assert error.value.detail == "Incorrect username or password"


def test_token_resolves_to_the_database_user(db_connection: Connection, settings: Settings) -> None:
    token = create_access_token(user_id=1, role="expert", settings=settings)

    user = get_user_from_token(db_connection, token, settings)

    assert (user["id"], user["username"], user["role"]) == (1, "expert_demo", "expert")
    assert "password_hash" not in user


def test_role_is_read_from_the_database_not_trusted_from_the_token(
    db_connection: Connection, settings: Settings
) -> None:
    token = create_access_token(user_id=2, role="expert", settings=settings)

    assert get_user_from_token(db_connection, token, settings)["role"] == "operator"


def test_token_of_a_deleted_user_is_rejected(db_connection: Connection, settings: Settings) -> None:
    token = create_access_token(user_id=2, role="operator", settings=settings)
    db_connection.execute(text("DELETE FROM users WHERE id = 2"))

    with pytest.raises(HTTPException) as error:
        get_user_from_token(db_connection, token, settings)

    assert error.value.status_code == 401


def test_invalid_token_is_rejected_with_401(db_connection: Connection, settings: Settings) -> None:
    with pytest.raises(HTTPException) as error:
        get_user_from_token(db_connection, "not-a-jwt", settings)

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}
