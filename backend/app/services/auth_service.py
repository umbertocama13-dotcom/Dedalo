from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException, status
from sqlalchemy import Connection

from app.config import Settings
from app.repositories import users_repository
from app.services.security import create_access_token, decode_access_token, hash_password, verify_password

INVALID_CREDENTIALS_DETAIL = "Incorrect username or password"


@lru_cache
def _dummy_password_hash() -> str:
    """Returns a throwaway bcrypt hash, computed lazily on first use (not at import)."""
    return hash_password("dummy-password-for-timing")


def authenticate_user(connection: Connection, username: str, password: str, settings: Settings) -> str:
    """Checks credentials and issues an access token.

    Args:
        connection: Open database connection.
        username: Username submitted at login.
        password: Plain-text password submitted at login.
        settings: Settings used to sign the token.

    Returns:
        A signed access token for the user.

    Raises:
        HTTPException: 400 with the same message for unknown user and wrong password.
    """
    user = users_repository.get_user_by_username(connection, username)
    if user is None:
        # Run bcrypt anyway: otherwise an unknown username answers much faster than
        # a wrong password, and response time would reveal which usernames exist.
        verify_password(password, _dummy_password_hash())
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_CREDENTIALS_DETAIL)

    if not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_CREDENTIALS_DETAIL)

    return create_access_token(user_id=user["id"], role=user["role"], settings=settings)


def get_user_from_token(connection: Connection, token: str, settings: Settings) -> dict[str, Any]:
    """Resolves a token to the current database user.

    The role is taken from the database, not from the token, so a role change or a
    deleted account takes effect immediately instead of when the token expires.

    Args:
        connection: Open database connection.
        token: Bearer token sent by the client.
        settings: Settings used to validate the token.

    Returns:
        The user row (id, username, role, created_at), without the password hash.

    Raises:
        HTTPException: 401 if the token is invalid or its user no longer exists.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token, settings)
    except jwt.InvalidTokenError:
        raise credentials_error from None

    user = users_repository.get_user_by_id(connection, payload.user_id)
    if user is None:
        raise credentials_error
    return user
