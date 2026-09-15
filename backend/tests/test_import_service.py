"""Integration tests for the CSV import on the seeded test database.

Seed facts used here: 36 diagnostics; family 3 is "Cella di saldatura robotizzata"
with phases 1-4 (ids 9-12); diagnostic 26 is a family-3 row without phase.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection, text

from app.repositories import diagnostics_repository
from app.services import import_service, knowledge_base_service
from app.services.csv_service import CSV_COLUMNS

EXPERT_ID = 1
HEADER = ";".join(CSV_COLUMNS)
NEW_GENERIC = ";;;;Il compressore si avvia di continuo;Compressore;Perdita sulla linea.;Cercare la perdita."
NEW_IN_PHASE = ";cella di saldatura robotizzata;3;;L'ugello si intasa;Ugello;Spruzzi.;Pulire l'ugello."


def csv_file(*lines: str) -> bytes:
    return "\r\n".join((HEADER, *lines)).encode("utf-8")


def count_diagnostics(connection: Connection) -> int:
    return connection.execute(text("SELECT COUNT(*) FROM diagnostics")).scalar_one()


def edited_row_26(connection: Connection, **changes: Any) -> str:
    """Returns diagnostic 26 as a CSV line, with some fields changed."""
    row = {**diagnostics_repository.get_diagnostic(connection, 26), **changes}
    return ";".join("" if row.get(column) is None else str(row[column]) for column in CSV_COLUMNS)


@pytest.fixture
def run(db_connection: Connection) -> Callable[..., Any]:
    def _run(data: bytes, dry_run: bool) -> Any:
        return import_service.import_diagnostics_csv(db_connection, data, created_by=EXPERT_ID, dry_run=dry_run)

    return _run


def test_preview_counts_changes_and_writes_nothing(db_connection: Connection, run: Callable[..., Any]) -> None:
    data = csv_file(NEW_GENERIC, NEW_IN_PHASE, edited_row_26(db_connection, affected_component="Motore nastro pallet"))

    report = run(data, dry_run=True)

    assert (report.applied, report.to_create, report.to_update, report.unchanged, report.errors) == (False, 2, 1, 0, [])
    assert count_diagnostics(db_connection) == 36
    assert diagnostics_repository.get_diagnostic(db_connection, 26)["affected_component"] == "Nastro trasportatore pallet"


def test_apply_creates_and_updates(db_connection: Connection, run: Callable[..., Any]) -> None:
    data = csv_file(NEW_GENERIC, NEW_IN_PHASE, edited_row_26(db_connection, affected_component="Motore nastro pallet"))

    report = run(data, dry_run=False)

    assert (report.applied, report.to_create, report.to_update) == (True, 2, 1)
    assert count_diagnostics(db_connection) == 38
    assert diagnostics_repository.get_diagnostic(db_connection, 26)["affected_component"] == "Motore nastro pallet"
    [new_in_phase] = diagnostics_repository.list_diagnostics(db_connection, search="ugello si intasa")
    assert (new_in_phase["family_id"], new_in_phase["cycle_phase_id"], new_in_phase["created_by"]) == (3, 11, EXPERT_ID)


def test_exporting_and_importing_the_same_file_changes_nothing(
    db_connection: Connection, run: Callable[..., Any]
) -> None:
    report = run(knowledge_base_service.export_csv(db_connection), dry_run=False)

    assert (report.to_create, report.to_update, report.unchanged, report.errors) == (0, 0, 36, [])


def test_the_template_can_be_imported_as_it_is(db_connection: Connection, run: Callable[..., Any]) -> None:
    report = run(knowledge_base_service.template_csv(db_connection), dry_run=True)

    assert (report.to_create, report.errors) == (3, [])


def test_moving_a_row_to_the_whole_family_clears_its_phase(db_connection: Connection, run: Callable[..., Any]) -> None:
    # Diagnostic 30 is scoped to phase 1 of family 3.
    row = diagnostics_repository.get_diagnostic(db_connection, 30)
    line = ";".join(
        "" if column in ("phase_number", "phase_name") or row.get(column) is None else str(row[column])
        for column in CSV_COLUMNS
    )

    run(csv_file(line), dry_run=False)

    assert diagnostics_repository.get_diagnostic(db_connection, 30)["cycle_phase_id"] is None


@pytest.mark.parametrize(
    ("line", "column", "message_part"),
    [
        (";Cella inventata;;;S;C;P;R", "family_name", "famiglia «Cella inventata» inesistente. Famiglie valide: «Cella di"),
        (";Cella di saldatura robotizzata;7;;S;C;P;R", "phase_number", "non ha una fase numero 7"),
        ("999;;;;S;C;P;R", "id", "l'id 999 non esiste"),
    ],
    ids=["unknown-family", "unknown-phase-number", "unknown-id"],
)
def test_database_checks_are_reported_per_row(
    run: Callable[..., Any], line: str, column: str, message_part: str
) -> None:
    report = run(csv_file(NEW_GENERIC, line), dry_run=True)

    [error] = report.errors
    assert (error.line, error.column) == (3, column)
    assert message_part in error.message
    assert report.to_create == 1


def test_one_error_blocks_the_whole_file(db_connection: Connection, run: Callable[..., Any]) -> None:
    with pytest.raises(HTTPException) as error:
        run(csv_file(NEW_GENERIC, ";Cella inventata;;;S;C;P;R"), dry_run=False)

    assert error.value.status_code == 400
    assert error.value.detail["applied"] is False
    assert [row_error["line"] for row_error in error.value.detail["errors"]] == [3]
    assert count_diagnostics(db_connection) == 36


def test_parsing_errors_and_database_errors_are_merged_in_line_order(run: Callable[..., Any]) -> None:
    report = run(csv_file(";Cella inventata;;;S;C;P;R", "abc;;;;S;C;P;R"), dry_run=True)

    assert [(error.line, error.column) for error in report.errors] == [(2, "family_name"), (3, "id")]


def test_file_too_large_is_rejected(run: Callable[..., Any]) -> None:
    with pytest.raises(HTTPException) as error:
        run(b"x" * (import_service.MAX_FILE_BYTES + 1), dry_run=True)

    assert error.value.status_code == 400
