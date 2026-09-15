from typing import Any

from sqlalchemy import Connection, text


def list_families(connection: Connection) -> list[dict[str, Any]]:
    """Lists all product families ordered by name.

    Args:
        connection: Open database connection.

    Returns:
        Family rows as dicts.
    """
    rows = connection.execute(
        text("SELECT id, family_name, description FROM product_families ORDER BY family_name")
    ).mappings().all()
    return [dict(row) for row in rows]


def get_family(connection: Connection, family_id: int) -> dict[str, Any] | None:
    """Fetches a single product family.

    Args:
        connection: Open database connection.
        family_id: Primary key of the family.

    Returns:
        The family row as a dict, or None if it does not exist.
    """
    row = connection.execute(
        text("SELECT id, family_name, description FROM product_families WHERE id = :family_id"),
        {"family_id": family_id},
    ).mappings().first()
    return dict(row) if row else None


def list_phases(connection: Connection, family_id: int) -> list[dict[str, Any]]:
    """Lists the cycle phases of a family in execution order.

    Args:
        connection: Open database connection.
        family_id: Family whose phases are requested.

    Returns:
        Phase rows as dicts, ordered by phase_number.
    """
    rows = connection.execute(
        text(
            "SELECT id, family_id, phase_number, phase_name FROM cycle_phases "
            "WHERE family_id = :family_id ORDER BY phase_number"
        ),
        {"family_id": family_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def list_all_phases(connection: Connection) -> list[dict[str, Any]]:
    """Lists the phases of every family, e.g. to resolve a whole CSV file with one query.

    Args:
        connection: Open database connection.

    Returns:
        Phase rows as dicts, ordered by family and phase number.
    """
    rows = connection.execute(
        text("SELECT id, family_id, phase_number, phase_name FROM cycle_phases ORDER BY family_id, phase_number")
    ).mappings().all()
    return [dict(row) for row in rows]


def get_phase(connection: Connection, phase_id: int) -> dict[str, Any] | None:
    """Fetches a single cycle phase, including the family it belongs to.

    Args:
        connection: Open database connection.
        phase_id: Primary key of the phase.

    Returns:
        The phase row as a dict, or None if it does not exist.
    """
    row = connection.execute(
        text("SELECT id, family_id, phase_number, phase_name FROM cycle_phases WHERE id = :phase_id"),
        {"phase_id": phase_id},
    ).mappings().first()
    return dict(row) if row else None
