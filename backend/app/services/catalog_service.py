from fastapi import HTTPException, status
from sqlalchemy import Connection

from app.repositories import catalog_repository
from app.schemas.catalog import FamilyOut, PhaseOut


def list_families(connection: Connection) -> list[FamilyOut]:
    """Lists all product families.

    Args:
        connection: Open database connection.

    Returns:
        The product families ordered by name.
    """
    return [FamilyOut.model_validate(row) for row in catalog_repository.list_families(connection)]


def list_phases(connection: Connection, family_id: int) -> list[PhaseOut]:
    """Lists the cycle phases of a product family.

    Args:
        connection: Open database connection.
        family_id: Family whose phases are requested.

    Returns:
        The phases in cycle order.

    Raises:
        HTTPException: 404 if the family does not exist.
    """
    _ensure_family_exists(connection, family_id)
    return [PhaseOut.model_validate(row) for row in catalog_repository.list_phases(connection, family_id)]


def validate_family_phase(connection: Connection, family_id: int | None, cycle_phase_id: int | None) -> None:
    """Checks an optional family/phase context.

    Both may be None (every family). A phase needs its family, and must belong to it.

    Args:
        connection: Open database connection.
        family_id: Selected product family, or None.
        cycle_phase_id: Selected cycle phase, or None.

    Raises:
        HTTPException: 404 if the family or the phase does not exist,
            400 if a phase is given without family or belongs to a different family.
    """
    if family_id is None:
        if cycle_phase_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="A cycle phase requires its product family"
            )
        return

    _ensure_family_exists(connection, family_id)
    if cycle_phase_id is None:
        return
    phase = catalog_repository.get_phase(connection, cycle_phase_id)
    if phase is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle phase not found")
    if phase["family_id"] != family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cycle phase does not belong to the selected product family",
        )


def _ensure_family_exists(connection: Connection, family_id: int) -> None:
    """Raises 404 if the product family does not exist.

    Args:
        connection: Open database connection.
        family_id: Family to check.

    Raises:
        HTTPException: 404 if the family does not exist.
    """
    if catalog_repository.get_family(connection, family_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product family not found")
