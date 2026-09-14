"""Integration tests for the catalog service on the seeded test database."""

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection

from app.services import catalog_service


def test_lists_all_families(db_connection: Connection) -> None:
    families = catalog_service.list_families(db_connection)

    assert {family.id for family in families} == {1, 2}


def test_lists_phases_of_a_family_in_cycle_order(db_connection: Connection) -> None:
    phases = catalog_service.list_phases(db_connection, family_id=2)

    assert [phase.id for phase in phases] == [5, 6, 7, 8]
    assert [phase.phase_number for phase in phases] == [1, 2, 3, 4]


def test_phases_of_unknown_family_is_404(db_connection: Connection) -> None:
    with pytest.raises(HTTPException) as error:
        catalog_service.list_phases(db_connection, family_id=999)

    assert error.value.status_code == 404


def test_coherent_family_and_phase_are_accepted(db_connection: Connection) -> None:
    catalog_service.validate_family_phase(db_connection, family_id=2, cycle_phase_id=7)


@pytest.mark.parametrize(
    ("family_id", "cycle_phase_id", "expected_status"),
    [(999, 1, 404), (1, 999, 404), (1, 7, 400)],
    ids=["unknown-family", "unknown-phase", "phase-of-another-family"],
)
def test_invalid_family_phase_combinations_are_rejected(
    db_connection: Connection, family_id: int, cycle_phase_id: int, expected_status: int
) -> None:
    with pytest.raises(HTTPException) as error:
        catalog_service.validate_family_phase(db_connection, family_id=family_id, cycle_phase_id=cycle_phase_id)

    assert error.value.status_code == expected_status
