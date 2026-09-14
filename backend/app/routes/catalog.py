from fastapi import APIRouter

from app.dependencies import CurrentUser, DbConnection
from app.schemas.catalog import FamilyOut, PhaseOut
from app.services import catalog_service

router = APIRouter(prefix="/families", tags=["catalog"])


@router.get("", response_model=list[FamilyOut])
def list_families(_: CurrentUser, connection: DbConnection) -> list[FamilyOut]:
    """Lists the product families."""
    return catalog_service.list_families(connection)


@router.get("/{family_id}/phases", response_model=list[PhaseOut])
def list_phases(family_id: int, _: CurrentUser, connection: DbConnection) -> list[PhaseOut]:
    """Lists the cycle phases of a product family."""
    return catalog_service.list_phases(connection, family_id)
