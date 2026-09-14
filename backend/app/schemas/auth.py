from typing import Literal

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Access token returned by the login endpoint (OAuth2 password flow format)."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Public view of a user: never includes the password hash."""

    id: int
    username: str
    role: Literal["expert", "operator"]
