"""User management endpoints (expert only)."""

from fastapi import APIRouter, status

from app.dependencies import DbConnection, ExpertUser
from app.schemas.auth import UserOut
from app.schemas.users import UserIn
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_: ExpertUser, connection: DbConnection) -> list[UserOut]:
    """Lists every user (expert only)."""
    return user_service.list_users(connection)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserIn, _: ExpertUser, connection: DbConnection) -> UserOut:
    """Creates an operator or expert account (expert only)."""
    return user_service.create_user(connection, body)
