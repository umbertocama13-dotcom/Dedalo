from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import Settings

# bcrypt only uses the first 72 bytes of a password; bcrypt>=5 raises instead of
# silently truncating, so the limit is checked explicitly.
BCRYPT_MAX_PASSWORD_BYTES = 72


@dataclass(frozen=True)
class TokenPayload:
    """Identity carried by a valid access token."""

    user_id: int
    role: str


def hash_password(password: str) -> str:
    """Hashes a password with bcrypt and a random salt.

    Args:
        password: Plain-text password.

    Returns:
        The bcrypt hash, safe to store in users.password_hash.

    Raises:
        ValueError: If the password exceeds bcrypt's 72-byte limit.
    """
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Checks a plain-text password against a stored bcrypt hash.

    Args:
        password: Plain-text password to check.
        password_hash: Hash stored in the database.

    Returns:
        True if the password matches. A password over the bcrypt limit can never
        match a stored hash, so it returns False instead of raising.
    """
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))


def create_access_token(user_id: int, role: str, settings: Settings, now: datetime | None = None) -> str:
    """Creates a signed JWT access token.

    Args:
        user_id: Id of the authenticated user.
        role: Role of the user at login time (informative: it is re-read from the DB on each request).
        settings: Settings with secret key, algorithm and expiry.
        now: Issue time; defaults to the current UTC time. Tests pass a past time to get expired tokens.

    Returns:
        The encoded token.
    """
    issued_at = now or datetime.now(UTC)
    payload = {
        # PyJWT requires "sub" to be a string.
        "sub": str(user_id),
        "role": role,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> TokenPayload:
    """Validates a JWT (signature, expiry, required claims) and extracts the identity.

    Args:
        token: Encoded token received from the client.
        settings: Settings with secret key and algorithm.

    Returns:
        The user id and role carried by the token.

    Raises:
        jwt.InvalidTokenError: If the token is malformed, tampered, expired or incomplete.
    """
    # algorithms is an explicit allow-list: never let the token header choose it.
    claims = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "role", "exp"]},
    )
    try:
        user_id = int(claims["sub"])
    except ValueError as error:
        raise jwt.InvalidTokenError("subject is not a user id") from error
    return TokenPayload(user_id=user_id, role=claims["role"])
