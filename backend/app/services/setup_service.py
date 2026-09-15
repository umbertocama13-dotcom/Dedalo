"""First-start setup of an installation without users (desktop app).

The installer ships no credentials: the person who opens the app first creates the
expert account. The setup endpoint works only while the users table is empty, so it
cannot be used to create extra accounts later.
"""

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import Connection

from app.repositories import users_repository
from app.schemas.users import SetupIn, SetupResult, UserIn
from app.services import import_service, user_service


def needs_setup(connection: Connection) -> bool:
    """Tells whether the application has no users yet.

    Args:
        connection: Open database connection.

    Returns:
        True if the first expert still has to be created.
    """
    return users_repository.count_users(connection) == 0


def create_first_expert(connection: Connection, data: SetupIn, sample_csv: Path | None) -> SetupResult:
    """Creates the first expert and optionally loads the sample diagnostics.

    Known limit: two setup requests sent at the very same moment could both create an
    expert. On a single-PC install only one person is looking at the setup screen.

    Args:
        connection: Open database connection with the request transaction.
        data: Username, password and sample-data choice.
        sample_csv: CSV file with the sample diagnostics, or None if not available.

    Returns:
        The new expert and how many sample diagnostics were loaded.

    Raises:
        HTTPException: 409 if a user already exists; 400 if the sample diagnostics
            were requested but are not available, or the password is too long.
    """
    if not needs_setup(connection):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Setup already completed")
    if data.load_sample_diagnostics and (sample_csv is None or not sample_csv.is_file()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sample diagnostics are not available in this installation",
        )

    expert = user_service.create_user(connection, UserIn(username=data.username, password=data.password, role="expert"))

    loaded = 0
    if data.load_sample_diagnostics:
        # Same code path as a manual CSV import: the sample data obeys exactly the same rules.
        report = import_service.import_diagnostics_csv(
            connection, sample_csv.read_bytes(), created_by=expert.id, dry_run=False
        )
        loaded = report.to_create
    return SetupResult(user=expert, sample_diagnostics_loaded=loaded)
