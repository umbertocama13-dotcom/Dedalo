from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import Settings
from app.services.security import (
    TokenPayload,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture
def jwt_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"jwt_secret_key": "unit-test-secret-at-least-32-bytes!!", "jwt_expire_minutes": 30}
    )


# --- Passwords ----------------------------------------------------------------


def test_hash_is_not_the_plain_password_and_verifies() -> None:
    password_hash = hash_password("expert123")

    assert password_hash != "expert123"
    assert password_hash.startswith("$2b$")
    assert verify_password("expert123", password_hash)


def test_wrong_password_does_not_verify() -> None:
    assert not verify_password("wrong", hash_password("expert123"))


def test_same_password_gets_different_hashes() -> None:
    # bcrypt adds a random salt, so equal passwords are not recognizable in the DB.
    assert hash_password("expert123") != hash_password("expert123")


def test_seed_hash_verifies() -> None:
    seed_hash = "$2b$12$OYQxnobvq0uEZTbtolJBmOXE7HVK82PCdwCbqRbCjCRqXqutt2DHm"

    assert verify_password("operator123", seed_hash)


def test_password_longer_than_bcrypt_limit_is_rejected_without_crashing() -> None:
    too_long = "a" * 73

    assert not verify_password(too_long, hash_password("expert123"))
    with pytest.raises(ValueError):
        hash_password(too_long)


# --- Tokens -------------------------------------------------------------------


def test_token_round_trip(jwt_settings: Settings) -> None:
    token = create_access_token(user_id=2, role="operator", settings=jwt_settings)

    assert decode_access_token(token, jwt_settings) == TokenPayload(user_id=2, role="operator")


def test_expired_token_is_rejected(jwt_settings: Settings) -> None:
    issued_long_ago = datetime.now(UTC) - timedelta(minutes=31)
    token = create_access_token(user_id=2, role="operator", settings=jwt_settings, now=issued_long_ago)

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, jwt_settings)


def test_token_signed_with_another_key_is_rejected(jwt_settings: Settings) -> None:
    other = jwt_settings.model_copy(update={"jwt_secret_key": "another-secret-key-of-32-bytes-min!!"})
    token = create_access_token(user_id=1, role="expert", settings=other)

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, jwt_settings)


def test_tampered_token_is_rejected(jwt_settings: Settings) -> None:
    token = create_access_token(user_id=2, role="operator", settings=jwt_settings)
    header, payload, signature = token.split(".")
    tampered = ".".join([header, payload, signature[::-1]])

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered, jwt_settings)


def test_token_without_required_claims_is_rejected(jwt_settings: Settings) -> None:
    token = jwt.encode({"foo": "bar"}, jwt_settings.jwt_secret_key, algorithm=jwt_settings.jwt_algorithm)

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, jwt_settings)
