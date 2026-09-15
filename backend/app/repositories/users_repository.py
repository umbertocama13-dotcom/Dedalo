from typing import Any

from sqlalchemy import Connection, text


def get_user_by_username(connection: Connection, username: str) -> dict[str, Any] | None:
    """Fetches a user by username, including the password hash for login checks.

    The comparison ignores case: MySQL's collation and SQLite's NOCASE column both do.

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


def count_users(connection: Connection) -> int:
    """Counts the users, used to know whether the first-start setup is still needed.

    Args:
        connection: Open database connection.

    Returns:
        The number of users.
    """
    return int(connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one())


def list_users(connection: Connection) -> list[dict[str, Any]]:
    """Lists every user, without password hashes.

    Args:
        connection: Open database connection.

    Returns:
        User rows as dicts, ordered by username.
    """
    rows = connection.execute(text("SELECT id, username, role, created_at FROM users ORDER BY username")).mappings().all()
    return [dict(row) for row in rows]


def insert_user(connection: Connection, username: str, password_hash: str, role: str) -> int:
    """Inserts a user.

    Args:
        connection: Open database connection.
        username: Unique username (case-insensitive).
        password_hash: bcrypt hash of the password, never the plain text.
        role: "expert" or "operator".

    Returns:
        The id of the new user.
    """
    result = connection.execute(
        text("INSERT INTO users (username, password_hash, role) VALUES (:username, :password_hash, :role)"),
        {"username": username, "password_hash": password_hash, "role": role},
    )
    return int(result.lastrowid)
