from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import AppSettings, CurrentUser, DbConnection
from app.schemas.auth import TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], connection: DbConnection, settings: AppSettings
) -> TokenResponse:
    """Exchanges username and password (form fields) for a bearer token."""
    token = auth_service.authenticate_user(connection, form.username, form.password, settings)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def read_current_user(user: CurrentUser) -> UserOut:
    """Returns the authenticated user, so the frontend knows the role."""
    return user
