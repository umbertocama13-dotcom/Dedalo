"""First-start setup endpoints: public, but POST /setup works only while there are no users."""

from pathlib import Path

from fastapi import APIRouter, status

from app.dependencies import AppSettings, DbConnection
from app.schemas.users import SetupIn, SetupResult, SetupStatus
from app.services import setup_service

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatus)
def get_setup_status(connection: DbConnection) -> SetupStatus:
    """Tells the frontend whether to show the first-start screen."""
    return SetupStatus(needs_setup=setup_service.needs_setup(connection))


@router.post("", response_model=SetupResult, status_code=status.HTTP_201_CREATED)
def run_setup(body: SetupIn, connection: DbConnection, settings: AppSettings) -> SetupResult:
    """Creates the first expert (409 once any user exists)."""
    sample_csv = Path(settings.sample_diagnostics_csv) if settings.sample_diagnostics_csv else None
    return setup_service.create_first_expert(connection, body, sample_csv)
