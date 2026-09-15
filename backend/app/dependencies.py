"""FastAPI dependencies shared by the routes.

Objects created once at startup (settings, matcher, AI provider) are read from
app.state instead of module globals, so each create_app() call — including the
ones in tests — gets its own independent configuration.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import Connection

from app.config import Settings
from app.db import get_connection
from app.schemas.auth import UserOut
from app.services import auth_service
from app.services.ai.base import AIProvider
from app.services.matching.base import Matcher

# tokenUrl tells Swagger UI where its "Authorize" button sends username and password.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_app_settings(request: Request) -> Settings:
    """Returns the settings the application was created with."""
    return request.app.state.settings


def get_matcher(request: Request) -> Matcher:
    """Returns the matching engine created at startup."""
    return request.app.state.matcher


def get_ai_provider(request: Request) -> AIProvider:
    """Returns the AI provider created at startup."""
    return request.app.state.ai_provider


DbConnection = Annotated[Connection, Depends(get_connection)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
AppMatcher = Annotated[Matcher, Depends(get_matcher)]
AppAIProvider = Annotated[AIProvider, Depends(get_ai_provider)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], connection: DbConnection, settings: AppSettings
) -> UserOut:
    """Resolves the bearer token to the current user.

    FastAPI caches dependencies within a request, so this uses the same
    connection (and transaction) as the route that requires it.

    Args:
        token: Bearer token from the Authorization header (missing header -> 401).
        connection: Request database connection.
        settings: Application settings.

    Returns:
        The authenticated user, with the role read from the database.

    Raises:
        HTTPException: 401 if the token is invalid or the user no longer exists.
    """
    return UserOut.model_validate(auth_service.get_user_from_token(connection, token, settings))


CurrentUser = Annotated[UserOut, Depends(get_current_user)]


def require_role(*allowed_roles: str) -> Callable[[UserOut], UserOut]:
    """Builds a dependency that lets through only users with one of the given roles.

    Args:
        *allowed_roles: Roles authorized to call the endpoint.

    Returns:
        A dependency returning the current user, or raising 403 for other roles.
    """

    def dependency(user: CurrentUser) -> UserOut:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency


ExpertUser = Annotated[UserOut, Depends(require_role("expert"))]
