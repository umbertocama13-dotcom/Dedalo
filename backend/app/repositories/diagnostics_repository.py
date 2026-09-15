"""Data access for the diagnostics table.

Integrity errors (unknown foreign keys, phase of another family, phase without family)
are not caught here: they propagate as sqlalchemy.exc.IntegrityError and the service
layer validates the context before writing.

Update/delete functions return ``rowcount > 0``. The SQLAlchemy PyMySQL dialect
enables MySQL's FOUND_ROWS flag, and SQLite always counts matched rows, so an
update that sets identical values still returns True instead of looking like a 404.

The SQL is shared by MySQL and SQLite: no dialect-specific syntax is used.
"""

from typing import Any

from sqlalchemy import Connection, text

# Family and phase names are joined in, so callers can show and export them without extra queries.
_SELECT_DIAGNOSTICS = (
    "SELECT d.id, d.symptom_description, d.affected_component, d.probable_cause, d.recommended_solution, "
    "       d.family_id, f.family_name, d.cycle_phase_id, p.phase_number, p.phase_name, "
    "       d.created_by, d.created_at, d.updated_at "
    "FROM diagnostics d "
    "LEFT JOIN product_families f ON f.id = d.family_id "
    "LEFT JOIN cycle_phases p ON p.id = d.cycle_phase_id "
)


def list_candidates(connection: Connection, family_id: int, cycle_phase_id: int | None) -> list[dict[str, Any]]:
    """Loads the diagnostics that apply to the operator's context.

    A row applies when its family is NULL (generic) or the selected one. When a phase
    is selected, rows scoped to other phases are excluded; without a phase, every row
    of the family applies, since the operator does not know where the fault is.

    Args:
        connection: Open database connection.
        family_id: Product family selected by the operator.
        cycle_phase_id: Cycle phase selected by the operator, or None if unknown.

    Returns:
        One dict per diagnostic, with keys matching ``MatchCandidate``.
    """
    rows = connection.execute(
        text(
            "SELECT d.id AS diagnostic_id, d.symptom_description, d.affected_component, "
            "       d.probable_cause, d.recommended_solution, d.family_id, d.cycle_phase_id, "
            "       p.phase_number, p.phase_name "
            "FROM diagnostics d "
            "LEFT JOIN cycle_phases p ON p.id = d.cycle_phase_id "
            "WHERE (d.family_id IS NULL OR d.family_id = :family_id) "
            "  AND (:cycle_phase_id IS NULL OR d.cycle_phase_id IS NULL OR d.cycle_phase_id = :cycle_phase_id) "
            "ORDER BY d.id"
        ),
        {"family_id": family_id, "cycle_phase_id": cycle_phase_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def list_symptom_descriptions(connection: Connection) -> list[str]:
    """Lists every distinct symptom text, used to pre-compute embeddings at startup.

    Args:
        connection: Open database connection.

    Returns:
        The distinct symptom descriptions.
    """
    return list(connection.execute(text("SELECT DISTINCT symptom_description FROM diagnostics")).scalars().all())


def list_diagnostics(
    connection: Connection,
    family_id: int | None = None,
    cycle_phase_id: int | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Lists diagnostics with optional exact filters and a free-text search.

    Args:
        connection: Open database connection.
        family_id: Only rows scoped to this family.
        cycle_phase_id: Only rows scoped to this phase.
        search: Substring searched in symptom, component, cause and solution.

    Returns:
        Diagnostic rows as dicts, ordered by id.
    """
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if family_id is not None:
        conditions.append("d.family_id = :family_id")
        params["family_id"] = family_id
    if cycle_phase_id is not None:
        conditions.append("d.cycle_phase_id = :cycle_phase_id")
        params["cycle_phase_id"] = cycle_phase_id
    if search:
        # An explicit ESCAPE character: MySQL defaults to backslash, SQLite has no default.
        conditions.append(
            "(d.symptom_description LIKE :pattern ESCAPE '!' OR d.affected_component LIKE :pattern ESCAPE '!' "
            " OR d.probable_cause LIKE :pattern ESCAPE '!' OR d.recommended_solution LIKE :pattern ESCAPE '!')"
        )
        params["pattern"] = f"%{_escape_like(search)}%"

    # Only fixed SQL fragments are joined here; every user value travels as a bound parameter.
    where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
    rows = connection.execute(text(f"{_SELECT_DIAGNOSTICS}{where}ORDER BY d.id"), params).mappings().all()
    return [dict(row) for row in rows]


def get_diagnostic(connection: Connection, diagnostic_id: int) -> dict[str, Any] | None:
    """Fetches a single diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Primary key of the diagnostic.

    Returns:
        The diagnostic row as a dict, or None if it does not exist.
    """
    row = connection.execute(
        text(f"{_SELECT_DIAGNOSTICS}WHERE d.id = :diagnostic_id"), {"diagnostic_id": diagnostic_id}
    ).mappings().first()
    return dict(row) if row else None


def insert_diagnostic(
    connection: Connection,
    symptom_description: str,
    affected_component: str,
    probable_cause: str,
    recommended_solution: str,
    family_id: int | None,
    cycle_phase_id: int | None,
    created_by: int,
) -> int:
    """Inserts a diagnostic.

    Args:
        connection: Open database connection.
        symptom_description: Symptom as reported on the line.
        affected_component: Component involved in the fault.
        probable_cause: Cause of the fault.
        recommended_solution: Corrective procedure.
        family_id: Family the row applies to, or None for every family.
        cycle_phase_id: Phase the row applies to, or None for the whole family.
        created_by: Id of the expert creating the row.

    Returns:
        The id of the new diagnostic.
    """
    result = connection.execute(
        text(
            "INSERT INTO diagnostics "
            "(symptom_description, affected_component, probable_cause, recommended_solution, "
            " family_id, cycle_phase_id, created_by) "
            "VALUES (:symptom_description, :affected_component, :probable_cause, :recommended_solution, "
            "        :family_id, :cycle_phase_id, :created_by)"
        ),
        {
            "symptom_description": symptom_description,
            "affected_component": affected_component,
            "probable_cause": probable_cause,
            "recommended_solution": recommended_solution,
            "family_id": family_id,
            "cycle_phase_id": cycle_phase_id,
            "created_by": created_by,
        },
    )
    return int(result.lastrowid)


def update_diagnostic(
    connection: Connection,
    diagnostic_id: int,
    symptom_description: str,
    affected_component: str,
    probable_cause: str,
    recommended_solution: str,
    family_id: int | None,
    cycle_phase_id: int | None,
) -> bool:
    """Replaces the editable fields of a diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Primary key of the diagnostic.
        symptom_description: New symptom text.
        affected_component: New component.
        probable_cause: New cause.
        recommended_solution: New procedure.
        family_id: New family, or None for every family.
        cycle_phase_id: New phase, or None for the whole family.

    Returns:
        True if the diagnostic exists, False otherwise.
    """
    result = connection.execute(
        text(
            "UPDATE diagnostics SET symptom_description = :symptom_description, "
            "affected_component = :affected_component, probable_cause = :probable_cause, "
            "recommended_solution = :recommended_solution, family_id = :family_id, "
            # Set explicitly: SQLite has no ON UPDATE CURRENT_TIMESTAMP.
            "cycle_phase_id = :cycle_phase_id, updated_at = CURRENT_TIMESTAMP WHERE id = :diagnostic_id"
        ),
        {
            "diagnostic_id": diagnostic_id,
            "symptom_description": symptom_description,
            "affected_component": affected_component,
            "probable_cause": probable_cause,
            "recommended_solution": recommended_solution,
            "family_id": family_id,
            "cycle_phase_id": cycle_phase_id,
        },
    )
    return result.rowcount > 0


def delete_diagnostic(connection: Connection, diagnostic_id: int) -> bool:
    """Deletes a diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Primary key of the diagnostic.

    Returns:
        True if a row was deleted, False if it did not exist.
    """
    result = connection.execute(
        text("DELETE FROM diagnostics WHERE id = :diagnostic_id"), {"diagnostic_id": diagnostic_id}
    )
    return result.rowcount > 0


def _escape_like(value: str) -> str:
    """Escapes LIKE wildcards so a search for "50%" does not match everything.

    Args:
        value: Raw search text.

    Returns:
        The text with "!", "%" and "_" escaped with "!", the ESCAPE character of the query.
    """
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")
