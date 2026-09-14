from typing import Any

from sqlalchemy import Connection, text


def get_user_by_username(connection: Connection, username: str) -> dict[str, Any] | None:
    """Fetches a user by username, including the password hash for login checks.

    Args:
        connection: Open database connection.
        username: Username to look up.

    Returns:
        The user row as a dict, or None if no user has that username.
    """
    row = connection.execute(
        text("SELECT id, username, password_hash, role, created_at FROM users WHERE username = :username"),
        {"username": username},
    ).mappings().first()
    return dict(row) if row else None


def get_user_by_id(connection: Connection, user_id: int) -> dict[str, Any] | None:
    """Fetches a user by id, without the password hash.

    Args:
        connection: Open database connection.
        user_id: Primary key of the user.

    Returns:
        The user row as a dict, or None if the user does not exist.
    """
    row = connection.execute(
        text("SELECT id, username, role, created_at FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    ).mappings().first()
    return dict(row) if row else None
