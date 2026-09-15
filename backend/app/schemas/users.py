from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.auth import UserOut

# Letters, digits, dot, dash and underscore: no spaces, so a username is never ambiguous to type.
USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"
MIN_PASSWORD_LENGTH = 8


class UserIn(BaseModel):
    """Fields an expert provides to create a user."""

    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    # Not stripped: spaces are valid password characters. The 72-byte bcrypt limit is checked when hashing.
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    role: Literal["expert", "operator"]


class SetupIn(BaseModel):
    """First-start setup: the first expert and whether to load the sample diagnostics."""

    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    load_sample_diagnostics: bool = True


class SetupStatus(BaseModel):
    """Whether the application still needs its first expert."""

    needs_setup: bool


class SetupResult(BaseModel):
    """Outcome of the first-start setup."""

    user: UserOut
    sample_diagnostics_loaded: int
