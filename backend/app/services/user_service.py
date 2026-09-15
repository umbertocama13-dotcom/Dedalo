"""User management (expert only): list and create users.

Status codes: 400 for a password over the bcrypt limit, 409 for a username already taken.
"""

from fastapi import HTTPException, status
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.repositories import users_repository
from app.schemas.auth import UserOut
from app.schemas.users import UserIn
from app.services.security import hash_password


def list_users(connection: Connection) -> list[UserOut]:
    """Lists every user.

    Args:
        connection: Open database connection.

    Returns:
        The users ordered by username, without password hashes.
    """
    return [UserOut.model_validate(row) for row in users_repository.list_users(connection)]


def create_user(connection: Connection, data: UserIn) -> UserOut:
    """Creates a user with a bcrypt-hashed password.

    Args:
        connection: Open database connection.
        data: Validated username, password and role.

    Returns:
        The new user.

    Raises:
        HTTPException: 400 if the password exceeds bcrypt's 72-byte limit,
            409 if the username is already taken (ignoring case).
    """
    try:
        password_hash = hash_password(data.password)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password too long: at most 72 bytes"
        ) from error

    if users_repository.get_user_by_username(connection, data.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    try:
        new_id = users_repository.insert_user(connection, data.username, password_hash, data.role)
    except IntegrityError as error:
        # Two requests creating the same username at the same moment: the UNIQUE constraint decides.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from error
    return UserOut(id=new_id, username=data.username, role=data.role)
