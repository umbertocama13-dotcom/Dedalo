"""The database itself enforces the rules, on MySQL and on SQLite.

Services validate before writing; these tests prove the constraints hold even for a
write that bypasses them. On SQLite they also prove that PRAGMA foreign_keys is on.
"""

from typing import Any

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from app.repositories import diagnostics_repository

# PyMySQL reports a CHECK violation (MySQL error 3819) as OperationalError, while FK and
# UNIQUE violations and every SQLite constraint are IntegrityError: both mean "rejected".
CONSTRAINT_ERRORS = (IntegrityError, OperationalError)

INSERT_DIAGNOSTIC = text(
    "INSERT INTO diagnostics (symptom_description, affected_component, probable_cause, "
    "recommended_solution, family_id, cycle_phase_id, created_by) "
    "VALUES ('s', 'c', 'p', 'r', :family_id, :cycle_phase_id, :created_by)"
)


@pytest.mark.parametrize(
    "values",
    [
        {"family_id": None, "cycle_phase_id": 1, "created_by": 1},
        {"family_id": 1, "cycle_phase_id": 7, "created_by": 1},
        {"family_id": 99, "cycle_phase_id": None, "created_by": 1},
        {"family_id": None, "cycle_phase_id": None, "created_by": 99},
    ],
    ids=["phase-without-family", "phase-of-another-family", "unknown-family", "unknown-author"],
)
def test_incoherent_rows_are_rejected(db_connection: Connection, values: dict[str, Any]) -> None:
    with pytest.raises(CONSTRAINT_ERRORS):
        db_connection.execute(INSERT_DIAGNOSTIC, values)


@pytest.mark.parametrize(
    "values",
    [
        {"family_id": None, "cycle_phase_id": None, "created_by": 1},
        {"family_id": 3, "cycle_phase_id": None, "created_by": 1},
        {"family_id": 3, "cycle_phase_id": 11, "created_by": 1},
    ],
    ids=["generic", "family", "phase"],
)
def test_every_scope_is_accepted(db_connection: Connection, values: dict[str, Any]) -> None:
    db_connection.execute(INSERT_DIAGNOSTIC, values)


def test_usernames_are_unique_regardless_of_case(db_connection: Connection) -> None:
    with pytest.raises(IntegrityError):
        db_connection.execute(
            text("INSERT INTO users (username, password_hash, role) VALUES ('EXPERT_DEMO', 'x', 'operator')")
        )


def test_unknown_role_is_rejected(db_connection: Connection) -> None:
    # MySQL in strict mode rejects an invalid ENUM value; SQLite relies on the CHECK constraint.
    with pytest.raises((*CONSTRAINT_ERRORS, DataError)):
        db_connection.execute(text("INSERT INTO users (username, password_hash, role) VALUES ('nuovo', 'x', 'admin')"))


def test_update_refreshes_updated_at(db_connection: Connection) -> None:
    db_connection.execute(text("UPDATE diagnostics SET updated_at = '2000-01-01 00:00:00' WHERE id = 1"))
    row = diagnostics_repository.get_diagnostic(db_connection, 1)

    diagnostics_repository.update_diagnostic(
        db_connection,
        1,
        row["symptom_description"],
        row["affected_component"],
        row["probable_cause"],
        row["recommended_solution"],
        row["family_id"],
        row["cycle_phase_id"],
    )

    assert str(diagnostics_repository.get_diagnostic(db_connection, 1)["updated_at"]) > "2000-01-01 00:00:00"


@pytest.mark.parametrize("search", ["%", "_", "!", "!%"], ids=["percent", "underscore", "escape-char", "escaped-percent"])
def test_like_wildcards_are_searched_literally(db_connection: Connection, search: str) -> None:
    # None of these characters appears in the seed texts.
    assert diagnostics_repository.list_diagnostics(db_connection, search=search) == []


def test_search_finds_a_literal_underscore(db_connection: Connection) -> None:
    db_connection.execute(
        text(
            "INSERT INTO diagnostics (symptom_description, affected_component, probable_cause, recommended_solution, created_by) "
            "VALUES ('Allarme ERR_42 sul pannello', 'HMI', 'p', 'r', 1)"
        )
    )

    [found] = diagnostics_repository.list_diagnostics(db_connection, search="ERR_42")

    assert found["symptom_description"] == "Allarme ERR_42 sul pannello"
    assert diagnostics_repository.list_diagnostics(db_connection, search="ERRX42") == []
