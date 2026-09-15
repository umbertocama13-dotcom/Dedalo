"""CSV import of diagnostics: preview or all-or-nothing apply.

Rows with an id update that diagnostic, rows without id create a new one, and
diagnostics missing from the file are left untouched: a CSV never deletes anything.
Error messages are in Italian because the expert reads them directly.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Connection

from app.repositories import catalog_repository, diagnostics_repository
from app.schemas.knowledge_base import ImportReport, ImportRowError
from app.services.csv_service import CsvRow, parse_diagnostics_csv

MAX_FILE_BYTES = 2_000_000

_EDITABLE_FIELDS = (
    "symptom_description",
    "affected_component",
    "probable_cause",
    "recommended_solution",
    "family_id",
    "cycle_phase_id",
)


def import_diagnostics_csv(connection: Connection, data: bytes, created_by: int, dry_run: bool) -> ImportReport:
    """Validates a CSV file and, unless it is a dry run, writes it.

    Args:
        connection: Open database connection with the request transaction.
        data: Raw CSV file content.
        created_by: Id of the expert importing the file, stored on new rows.
        dry_run: If True, only report what would change.

    Returns:
        The report. ``applied`` is True only when the rows were written.

    Raises:
        HTTPException: 400 if the file is larger than MAX_FILE_BYTES, or with the report
            as detail if the file has errors and dry_run is False.
    """
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File troppo grande: il massimo è {MAX_FILE_BYTES // 1_000_000} MB.",
        )
    parsed = parse_diagnostics_csv(data)
    errors = [ImportRowError(line=error.line, column=error.column, message=error.message) for error in parsed.errors]

    families = {row["family_name"].casefold(): row for row in catalog_repository.list_families(connection)}
    phases = {(row["family_id"], row["phase_number"]): row for row in catalog_repository.list_all_phases(connection)}
    existing = {row["id"]: row for row in diagnostics_repository.list_diagnostics(connection)}

    to_create: list[dict[str, Any]] = []
    to_update: list[tuple[int, dict[str, Any]]] = []
    unchanged = 0
    for row in parsed.rows:
        fields, row_errors = _resolve(row, families, phases, existing)
        errors.extend(row_errors)
        if fields is None:
            continue
        if row.id is None:
            to_create.append(fields)
        elif any(existing[row.id][name] != value for name, value in fields.items()):
            to_update.append((row.id, fields))
        else:
            unchanged += 1

    errors.sort(key=lambda error: error.line)
    report = ImportReport(
        applied=False, to_create=len(to_create), to_update=len(to_update), unchanged=unchanged, errors=errors
    )
    if dry_run:
        return report
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=report.model_dump())

    # Every write runs in the request transaction: if one fails, get_connection rolls back all of them.
    for fields in to_create:
        diagnostics_repository.insert_diagnostic(connection, **fields, created_by=created_by)
    for diagnostic_id, fields in to_update:
        diagnostics_repository.update_diagnostic(connection, diagnostic_id, **fields)
    return report.model_copy(update={"applied": True})


def _resolve(
    row: CsvRow,
    families: dict[str, dict[str, Any]],
    phases: dict[tuple[int, int], dict[str, Any]],
    existing: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[ImportRowError]]:
    """Turns a parsed row into database fields, checking names and ids.

    Args:
        row: Row already validated by the CSV parser.
        families: Families by casefolded name (names are unique case-insensitively in MySQL).
        phases: Phases by (family id, phase number).
        existing: Current diagnostics by id.

    Returns:
        The fields to write (None if the row has errors) and the errors of the row.
    """
    errors = []
    family_id = cycle_phase_id = None

    if row.family_name is not None:
        family = families.get(row.family_name.casefold())
        if family is None:
            valid_names = ", ".join(sorted(f"«{item['family_name']}»" for item in families.values())) or "nessuna"
            errors.append(
                ImportRowError(
                    line=row.line,
                    column="family_name",
                    message=f"famiglia «{row.family_name}» inesistente. Famiglie valide: {valid_names}.",
                )
            )
        else:
            family_id = family["id"]
            if row.phase_number is not None:
                phase = phases.get((family_id, row.phase_number))
                if phase is None:
                    errors.append(
                        ImportRowError(
                            line=row.line,
                            column="phase_number",
                            message=f"la famiglia «{family['family_name']}» non ha una fase numero {row.phase_number}.",
                        )
                    )
                else:
                    cycle_phase_id = phase["id"]

    if row.id is not None and row.id not in existing:
        errors.append(
            ImportRowError(
                line=row.line,
                column="id",
                message=f"l'id {row.id} non esiste: lascia la cella vuota per creare una nuova riga.",
            )
        )

    if errors:
        return None, errors
    values = {
        "symptom_description": row.symptom_description,
        "affected_component": row.affected_component,
        "probable_cause": row.probable_cause,
        "recommended_solution": row.recommended_solution,
        "family_id": family_id,
        "cycle_phase_id": cycle_phase_id,
    }
    return {name: values[name] for name in _EDITABLE_FIELDS}, []
