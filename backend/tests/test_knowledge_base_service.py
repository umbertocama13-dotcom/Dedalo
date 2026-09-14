"""Integration tests for knowledge base management on the seeded test database."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection

from app.repositories import diagnostics_repository
from app.schemas.knowledge_base import BaseDiagnosticIn, ExceptionIn
from app.services import knowledge_base_service as kb

EXPERT_ID = 1


def assert_http_error(call: Callable[[], Any], expected_status: int) -> None:
    with pytest.raises(HTTPException) as error:
        call()
    assert error.value.status_code == expected_status


@pytest.fixture
def diagnostic_data() -> BaseDiagnosticIn:
    return BaseDiagnosticIn(
        symptom_description="L'avvitatore non raggiunge la coppia",
        affected_component="Avvitatore elettrico",
        probable_cause="Inserto usurato.",
        recommended_solution="Sostituire l'inserto.",
    )


@pytest.fixture
def exception_data() -> ExceptionIn:
    return ExceptionIn(
        family_id=1,
        cycle_phase_id=1,
        specific_cause="Causa specifica.",
        specific_solution="Soluzione specifica.",
    )


# --- Base diagnostics -----------------------------------------------------------


def test_lists_seeded_diagnostics(db_connection: Connection) -> None:
    assert [d.id for d in kb.list_diagnostics(db_connection)] == [1, 2, 3, 4]


def test_gets_a_diagnostic_or_404(db_connection: Connection) -> None:
    assert kb.get_diagnostic(db_connection, 3).affected_component == "Pinza pneumatica end-effector"
    assert_http_error(lambda: kb.get_diagnostic(db_connection, 999), 404)


def test_creates_a_diagnostic_owned_by_the_expert(
    db_connection: Connection, diagnostic_data: BaseDiagnosticIn
) -> None:
    created = kb.create_diagnostic(db_connection, diagnostic_data, created_by=EXPERT_ID)

    assert created.id > 4
    assert created.created_by == EXPERT_ID
    assert kb.get_diagnostic(db_connection, created.id).symptom_description == diagnostic_data.symptom_description


def test_updates_a_diagnostic_or_404(db_connection: Connection, diagnostic_data: BaseDiagnosticIn) -> None:
    updated = kb.update_diagnostic(db_connection, 1, diagnostic_data)

    assert (updated.id, updated.affected_component) == (1, "Avvitatore elettrico")
    assert_http_error(lambda: kb.update_diagnostic(db_connection, 999, diagnostic_data), 404)


def test_deleting_a_diagnostic_removes_its_exceptions(db_connection: Connection) -> None:
    kb.delete_diagnostic(db_connection, 2)

    assert_http_error(lambda: kb.get_diagnostic(db_connection, 2), 404)
    assert diagnostics_repository.get_exception(db_connection, 3) is None
    assert_http_error(lambda: kb.delete_diagnostic(db_connection, 2), 404)


# --- Exceptions -------------------------------------------------------------------


def test_lists_exceptions_of_a_diagnostic_or_404(db_connection: Connection) -> None:
    assert [e.id for e in kb.list_exceptions(db_connection, 3)] == [1]
    assert_http_error(lambda: kb.list_exceptions(db_connection, 999), 404)


def test_creates_an_exception(db_connection: Connection, exception_data: ExceptionIn) -> None:
    created = kb.create_exception(db_connection, 1, exception_data, created_by=EXPERT_ID)

    assert (created.base_diagnostic_id, created.family_id, created.cycle_phase_id) == (1, 1, 1)
    assert [e.id for e in kb.list_exceptions(db_connection, 1)] == [created.id]


@pytest.mark.parametrize(
    ("diagnostic_id", "overrides", "expected_status"),
    [
        (999, {}, 404),
        (1, {"family_id": 999}, 404),
        (1, {"cycle_phase_id": 999}, 404),
        (1, {"cycle_phase_id": 7}, 400),
        (3, {"cycle_phase_id": 2}, 409),
    ],
    ids=["unknown-diagnostic", "unknown-family", "unknown-phase", "phase-of-another-family", "duplicate-context"],
)
def test_invalid_exceptions_are_rejected(
    db_connection: Connection,
    exception_data: ExceptionIn,
    diagnostic_id: int,
    overrides: dict[str, int],
    expected_status: int,
) -> None:
    data = exception_data.model_copy(update=overrides)

    assert_http_error(lambda: kb.create_exception(db_connection, diagnostic_id, data, created_by=EXPERT_ID), expected_status)


def test_a_failed_insert_does_not_break_the_transaction(
    db_connection: Connection, exception_data: ExceptionIn
) -> None:
    duplicate = exception_data.model_copy(update={"cycle_phase_id": 2})
    assert_http_error(lambda: kb.create_exception(db_connection, 3, duplicate, created_by=EXPERT_ID), 409)

    created = kb.create_exception(db_connection, 3, exception_data, created_by=EXPERT_ID)

    assert created.cycle_phase_id == 1


def test_updates_an_exception(db_connection: Connection, exception_data: ExceptionIn) -> None:
    updated = kb.update_exception(db_connection, 3, 1, exception_data.model_copy(update={"cycle_phase_id": 3}))

    assert (updated.id, updated.cycle_phase_id, updated.specific_cause) == (1, 3, "Causa specifica.")


def test_update_exception_rejects_wrong_owner_and_duplicates(
    db_connection: Connection, exception_data: ExceptionIn
) -> None:
    # Exception 1 belongs to diagnostic 3, not 2.
    assert_http_error(lambda: kb.update_exception(db_connection, 2, 1, exception_data), 404)

    second = kb.create_exception(
        db_connection, 2, exception_data.model_copy(update={"family_id": 2, "cycle_phase_id": 6}), created_by=EXPERT_ID
    )
    # Diagnostic 2 already has exception 3 in family 2 / phase 5.
    moved_onto_existing = exception_data.model_copy(update={"family_id": 2, "cycle_phase_id": 5})
    assert_http_error(lambda: kb.update_exception(db_connection, 2, second.id, moved_onto_existing), 409)


def test_deletes_an_exception_only_through_its_diagnostic(db_connection: Connection) -> None:
    assert_http_error(lambda: kb.delete_exception(db_connection, 4, 1), 404)

    kb.delete_exception(db_connection, 3, 1)

    assert kb.list_exceptions(db_connection, 3) == []
