"""Knowledge base management: diagnostics CRUD and CSV export.

Status codes: 404 for a diagnostic in the path, or a referenced family/phase, that
does not exist; 400 for an incoherent scope (phase without family or of another family).
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Connection

from app.repositories import catalog_repository, diagnostics_repository
from app.schemas.knowledge_base import DiagnosticIn, DiagnosticOut
from app.services import csv_service
from app.services.catalog_service import validate_family_phase


def list_diagnostics(
    connection: Connection,
    family_id: int | None = None,
    cycle_phase_id: int | None = None,
    search: str | None = None,
) -> list[DiagnosticOut]:
    """Lists diagnostics, optionally filtered.

    Args:
        connection: Open database connection.
        family_id: Only rows scoped to this family.
        cycle_phase_id: Only rows scoped to this phase.
        search: Substring searched in symptom, component, cause and solution.

    Returns:
        The diagnostics ordered by id.
    """
    rows = diagnostics_repository.list_diagnostics(connection, family_id, cycle_phase_id, search)
    return [DiagnosticOut.model_validate(row) for row in rows]


def get_diagnostic(connection: Connection, diagnostic_id: int) -> DiagnosticOut:
    """Fetches one diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic.

    Returns:
        The diagnostic.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    row = diagnostics_repository.get_diagnostic(connection, diagnostic_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    return DiagnosticOut.model_validate(row)


def create_diagnostic(connection: Connection, data: DiagnosticIn, created_by: int) -> DiagnosticOut:
    """Creates a diagnostic.

    Args:
        connection: Open database connection.
        data: Validated diagnostic fields.
        created_by: Id of the expert creating it.

    Returns:
        The stored diagnostic, including generated id, names and timestamps.

    Raises:
        HTTPException: 404 if family or phase do not exist, 400 if the phase is not part of the family.
    """
    validate_family_phase(connection, data.family_id, data.cycle_phase_id)
    new_id = diagnostics_repository.insert_diagnostic(connection, **data.model_dump(), created_by=created_by)
    return get_diagnostic(connection, new_id)


def update_diagnostic(connection: Connection, diagnostic_id: int, data: DiagnosticIn) -> DiagnosticOut:
    """Replaces the fields of a diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic.
        data: New validated fields.

    Returns:
        The updated diagnostic.

    Raises:
        HTTPException: 404 if the diagnostic, family or phase do not exist,
            400 if the phase is not part of the family.
    """
    get_diagnostic(connection, diagnostic_id)
    validate_family_phase(connection, data.family_id, data.cycle_phase_id)
    diagnostics_repository.update_diagnostic(connection, diagnostic_id, **data.model_dump())
    return get_diagnostic(connection, diagnostic_id)


def delete_diagnostic(connection: Connection, diagnostic_id: int) -> None:
    """Deletes a diagnostic.

    Args:
        connection: Open database connection.
        diagnostic_id: Id of the diagnostic.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    if not diagnostics_repository.delete_diagnostic(connection, diagnostic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")


def export_csv(connection: Connection) -> bytes:
    """Exports every diagnostic in the CSV format accepted by the import.

    Args:
        connection: Open database connection.

    Returns:
        The CSV file content.
    """
    return csv_service.export_diagnostics_csv(diagnostics_repository.list_diagnostics(connection))


def template_csv(connection: Connection) -> bytes:
    """Builds a CSV template with one example row for each scope.

    The examples use a real family and phase of the database when there is one, so
    the template can be imported as it is to try the procedure.

    Args:
        connection: Open database connection.

    Returns:
        The CSV file content.
    """
    rows: list[dict[str, Any]] = [
        {
            "symptom_description": "Esempio: la macchina non si avvia",
            "affected_component": "Circuito di sicurezza",
            "probable_cause": "Esempio di causa valida per tutte le famiglie.",
            "recommended_solution": "Esempio di soluzione valida per tutte le famiglie.",
        }
    ]
    families = catalog_repository.list_families(connection)
    if families:
        family = families[0]
        rows.append(
            {
                "family_name": family["family_name"],
                "symptom_description": "Esempio: la cella non completa il ciclo",
                "affected_component": "Nastro trasportatore",
                "probable_cause": "Esempio di causa valida per tutta la famiglia.",
                "recommended_solution": "Esempio di soluzione valida per tutta la famiglia.",
            }
        )
        phases = catalog_repository.list_phases(connection, family["id"])
        if phases:
            rows.append(
                {
                    "family_name": family["family_name"],
                    "phase_number": phases[0]["phase_number"],
                    "phase_name": phases[0]["phase_name"],
                    "symptom_description": "Esempio: il pezzo non viene caricato",
                    "affected_component": "Sensore presenza pezzo",
                    "probable_cause": "Esempio di causa valida solo in questa fase.",
                    "recommended_solution": "Esempio di soluzione valida solo in questa fase.",
                }
            )
    return csv_service.export_diagnostics_csv(rows)
