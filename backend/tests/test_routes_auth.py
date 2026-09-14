from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from app.config import Settings
from app.services.security import create_access_token


def test_login_returns_a_bearer_token_usable_on_protected_endpoints(client: TestClient) -> None:
    response = client.post("/auth/login", data={"username": "operator_demo", "password": "operator123"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == {"id": 2, "username": "operator_demo", "role": "operator"}


@pytest.mark.parametrize(
    ("username", "password"),
    [("operator_demo", "wrong"), ("nobody", "operator123")],
    ids=["wrong-password", "unknown-user"],
)
def test_login_with_invalid_credentials_is_400(client: TestClient, username: str, password: str) -> None:
    response = client.post("/auth/login", data={"username": username, "password": password})

    assert response.status_code == 400
    assert response.json() == {"detail": "Incorrect username or password"}


def test_login_with_missing_fields_is_400(client: TestClient) -> None:
    assert client.post("/auth/login", data={"username": "operator_demo"}).status_code == 400


def test_missing_token_is_401_with_bearer_challenge(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def _encode(settings: Settings, secret: str | None = None, **claims: object) -> str:
    return jwt.encode(claims, secret or settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _in_five_minutes() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=5)


BAD_TOKENS: dict[str, Callable[[Settings], str]] = {
    "not-a-jwt": lambda s: "garbage",
    "expired": lambda s: create_access_token(
        user_id=2, role="operator", settings=s, now=datetime.now(UTC) - timedelta(minutes=s.jwt_expire_minutes + 1)
    ),
    "non-numeric-subject": lambda s: _encode(s, sub="operator_demo", role="operator", exp=_in_five_minutes()),
    "missing-role": lambda s: _encode(s, sub="2", exp=_in_five_minutes()),
    "wrong-signature": lambda s: _encode(
        s, secret="a-completely-different-secret-of-32b!", sub="2", role="operator", exp=_in_five_minutes()
    ),
}


@pytest.mark.parametrize("make_token", list(BAD_TOKENS.values()), ids=list(BAD_TOKENS))
def test_invalid_tokens_are_401(client: TestClient, settings: Settings, make_token: Callable[[Settings], str]) -> None:
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {make_token(settings)}"})

    assert response.status_code == 401


def test_token_of_a_deleted_user_is_401(
    client: TestClient, operator_headers: dict[str, str], db_connection: Connection
) -> None:
    db_connection.execute(text("DELETE FROM users WHERE id = 2"))

    assert client.get("/auth/me", headers=operator_headers).status_code == 401
