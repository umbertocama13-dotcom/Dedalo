"""Data access for base_diagnostics and diagnostic_exceptions.

Integrity errors (unknown foreign keys, duplicate exceptions) are not caught here:
they propagate as sqlalchemy.exc.IntegrityError and the service layer maps them
to HTTP status codes.

Update/delete functions return ``rowcount > 0``. The SQLAlchemy PyMySQL dialect
enables MySQL's FOUND_ROWS flag, so rowcount counts *matched* rows: an update
that sets identical values still returns True instead of looking like a 404.
"""

from typing import Any

from sqlalchemy import Connection, text

_BASE_COLUMNS = (
    "id, symptom_description, affected_component, probable_cause, "
    "recommended_solution, created_by, created_at, updated_at"
)
_EXCEPTION_COLUMNS = (
    "id, base_diagnostic_id, family_id, cycle_phase_id, specific_cause, "
    "specific_solution, created_by, created_at, updated_at"
)


def list_match_candidates(connection: Connection, family_id: int, cycle_phase_id: int) -> list[dict[str, Any]]:
    """Loads every base diagnostic with its exception for the given context, if any.

    The unique key (base_diagnostic_id, cycle_phase_id) guarantees the LEFT JOIN
    matches at most one exception per diagnostic, so rows are never duplicated.

    Args:
        connection: Open database connection.
        family_id: Product family selected by the operator.
        cycle_phase_id: Cycle phase selected by the operator.

    Returns:
        One dict per base diagnostic; exception_id, specific_cause and
        specific_solution are None when no exception applies.
    """
    rows = connection.execute(
        text(
            "SELECT b.id AS base_diagnostic_id, b.symptom_description, b.affected_component, "
            "       b.probable_cause, b.recommended_solution, "
            "       e.id AS exception_id, e.specific_cause, e.specific_solution "
            "FROM base_diagnostics b "
            "LEFT JOIN diagnostic_exceptions e "
            "       ON e.base_diagnostic_id = b.id "
            "      AND e.family_id = :family_id "
            "      AND e.cycle_phase_id = :cycle_phase_id "
            "ORDER BY b.id"
        ),
        {"family_id": family_id, "cycle_phase_id": cycle_phase_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def list_base_diagnostics(connection: Connection) -> list[dict[str, Any]]:
    """Lists all base diagnostics.

    Args:
        connection: Open database connection.

    Returns:
        Diagnostic rows as dicts, ordered by id.
    """
    rows = connection.execute(text(f"SELECT {_BASE_COLUMNS} FROM base_diagnostics ORDER BY id")).mappings().all()
    return [dict(row) for row in rows]


def get_base_diagnostic(connection: Connection, diagnostic_id: int) -> dict[str, Any] | None:
    """Fetches a single base diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Primary key of the diagnostic.

    Returns:
        The diagnostic row as a dict, or None if it does not exist.
    """
    row = connection.execute(
        text(f"SELECT {_BASE_COLUMNS} FROM base_diagnostics WHERE id = :diagnostic_id"),
        {"diagnostic_id": diagnostic_id},
    ).mappings().first()
    return dict(row) if row else None


def insert_base_diagnostic(
    connection: Connection,
    symptom_description: str,
    affected_component: str,
    probable_cause: str,
    recommended_solution: str,
    created_by: int,
) -> int:
    """Inserts a base diagnostic.

    Args:
        connection: Open database connection.
        symptom_description: Symptom as reported on the line.
        affected_component: Component involved in the fault.
        probable_cause: Generic cause of the fault.
        recommended_solution: Generic corrective procedure.
        created_by: Id of the expert creating the row.

    Returns:
        The id of the new diagnostic.
    """
    result = connection.execute(
        text(
            "INSERT INTO base_diagnostics "
            "(symptom_description, affected_component, probable_cause, recommended_solution, created_by) "
            "VALUES (:symptom_description, :affected_component, :probable_cause, :recommended_solution, :created_by)"
        ),
        {
            "symptom_description": symptom_description,
            "affected_component": affected_component,
            "probable_cause": probable_cause,
            "recommended_solution": recommended_solution,
            "created_by": created_by,
        },
    )
    return int(result.lastrowid)


def update_base_diagnostic(
    connection: Connection,
    diagnostic_id: int,
    symptom_description: str,
    affected_component: str,
    probable_cause: str,
    recommended_solution: str,
) -> bool:
    """Replaces the editable fields of a base diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Primary key of the diagnostic.
        symptom_description: New symptom text.
        affected_component: New component.
        probable_cause: New generic cause.
        recommended_solution: New generic procedure.

    Returns:
        True if the diagnostic exists, False otherwise.
    """
    result = connection.execute(
        text(
            "UPDATE base_diagnostics SET symptom_description = :symptom_description, "
            "affected_component = :affected_component, probable_cause = :probable_cause, "
            "recommended_solution = :recommended_solution WHERE id = :diagnostic_id"
        ),
        {
            "diagnostic_id": diagnostic_id,
            "symptom_description": symptom_description,
            "affected_component": affected_component,
            "probable_cause": probable_cause,
            "recommended_solution": recommended_solution,
        },
    )
    return result.rowcount > 0


def delete_base_diagnostic(connection: Connection, diagnostic_id: int) -> bool:
    """Deletes a base diagnostic; its exceptions are removed by ON DELETE CASCADE.

    Args:
        connection: Open database connection.
        diagnostic_id: Primary key of the diagnostic.

    Returns:
        True if a row was deleted, False if it did not exist.
    """
    result = connection.execute(
        text("DELETE FROM base_diagnostics WHERE id = :diagnostic_id"),
        {"diagnostic_id": diagnostic_id},
    )
    return result.rowcount > 0


def list_exceptions(connection: Connection, base_diagnostic_id: int) -> list[dict[str, Any]]:
    """Lists the exceptions attached to a base diagnostic.

    Args:
        connection: Open database connection.
        base_diagnostic_id: Diagnostic whose exceptions are requested.

    Returns:
        Exception rows as dicts, ordered by id.
    """
    rows = connection.execute(
        text(
            f"SELECT {_EXCEPTION_COLUMNS} FROM diagnostic_exceptions "
            "WHERE base_diagnostic_id = :base_diagnostic_id ORDER BY id"
        ),
        {"base_diagnostic_id": base_diagnostic_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def get_exception(connection: Connection, exception_id: int) -> dict[str, Any] | None:
    """Fetches a single diagnostic exception.

    Args:
        connection: Open database connection.
        exception_id: Primary key of the exception.

    Returns:
        The exception row as a dict, or None if it does not exist.
    """
    row = connection.execute(
        text(f"SELECT {_EXCEPTION_COLUMNS} FROM diagnostic_exceptions WHERE id = :exception_id"),
        {"exception_id": exception_id},
    ).mappings().first()
    return dict(row) if row else None


def insert_exception(
    connection: Connection,
    base_diagnostic_id: int,
    family_id: int,
    cycle_phase_id: int,
    specific_cause: str,
    specific_solution: str,
    created_by: int,
) -> int:
    """Inserts a context-specific override for a base diagnostic.

    Args:
        connection: Open database connection.
        base_diagnostic_id: Diagnostic being overridden.
        family_id: Product family the override applies to.
        cycle_phase_id: Cycle phase the override applies to (must belong to family_id).
        specific_cause: Cause valid in this context.
        specific_solution: Procedure valid in this context.
        created_by: Id of the expert creating the row.

    Returns:
        The id of the new exception.
    """
    result = connection.execute(
        text(
            "INSERT INTO diagnostic_exceptions "
            "(base_diagnostic_id, family_id, cycle_phase_id, specific_cause, specific_solution, created_by) "
            "VALUES (:base_diagnostic_id, :family_id, :cycle_phase_id, :specific_cause, :specific_solution, :created_by)"
        ),
        {
            "base_diagnostic_id": base_diagnostic_id,
            "family_id": family_id,
            "cycle_phase_id": cycle_phase_id,
            "specific_cause": specific_cause,
            "specific_solution": specific_solution,
            "created_by": created_by,
        },
    )
    return int(result.lastrowid)


def update_exception(
    connection: Connection,
    exception_id: int,
    family_id: int,
    cycle_phase_id: int,
    specific_cause: str,
    specific_solution: str,
) -> bool:
    """Replaces the editable fields of a diagnostic exception.

    Args:
        connection: Open database connection.
        exception_id: Primary key of the exception.
        family_id: New product family.
        cycle_phase_id: New cycle phase (must belong to family_id).
        specific_cause: New context-specific cause.
        specific_solution: New context-specific procedure.

    Returns:
        True if the exception exists, False otherwise.
    """
    result = connection.execute(
        text(
            "UPDATE diagnostic_exceptions SET family_id = :family_id, cycle_phase_id = :cycle_phase_id, "
            "specific_cause = :specific_cause, specific_solution = :specific_solution "
            "WHERE id = :exception_id"
        ),
        {
            "exception_id": exception_id,
            "family_id": family_id,
            "cycle_phase_id": cycle_phase_id,
            "specific_cause": specific_cause,
            "specific_solution": specific_solution,
        },
    )
    return result.rowcount > 0


def delete_exception(connection: Connection, exception_id: int) -> bool:
    """Deletes a diagnostic exception.

    Args:
        connection: Open database connection.
        exception_id: Primary key of the exception.

    Returns:
        True if a row was deleted, False if it did not exist.
    """
    result = connection.execute(
        text("DELETE FROM diagnostic_exceptions WHERE id = :exception_id"),
        {"exception_id": exception_id},
    )
    return result.rowcount > 0
