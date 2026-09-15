"""Integration tests for knowledge base management on the seeded test database.

Seed facts used here: 36 diagnostics; family 3 rows are ids 26-36; phase 10 rows are 34-35;
diagnostic 30 is scoped to family 3, phase 9 ("Ingresso pallet", number 1).
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import Connection

from app.schemas.knowledge_base import DiagnosticIn
from app.services import knowledge_base_service as kb

EXPERT_ID = 1


def assert_http_error(call: Callable[[], Any], expected_status: int) -> None:
    with pytest.raises(HTTPException) as error:
        call()
    assert error.value.status_code == expected_status


def data(**scope: int | None) -> DiagnosticIn:
    return DiagnosticIn(
        symptom_description="L'avvitatore non raggiunge la coppia",
        affected_component="Avvitatore elettrico",
        probable_cause="Inserto usurato.",
        recommended_solution="Sostituire l'inserto.",
        **scope,
    )


# --- Reading --------------------------------------------------------------------------


def test_lists_seeded_diagnostics_with_names(db_connection: Connection) -> None:
    diagnostics = kb.list_diagnostics(db_connection)

    assert [d.id for d in diagnostics] == list(range(1, 37))
    row_30 = diagnostics[29]
    assert (row_30.family_name, row_30.phase_number, row_30.phase_name) == ("Cella di saldatura robotizzata", 1, "Ingresso pallet")
    assert (diagnostics[0].family_id, diagnostics[0].family_name, diagnostics[0].phase_name) == (None, None, None)


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({"family_id": 3}, list(range(26, 37))),
        ({"cycle_phase_id": 10}, [34, 35]),
        ({"family_id": 3, "cycle_phase_id": 9}, [30]),
        ({"search": "%"}, []),
    ],
    ids=["family", "phase", "family-and-phase", "like-wildcard-is-literal"],
)
def test_filters(db_connection: Connection, filters: dict[str, Any], expected_ids: list[int]) -> None:
    assert [d.id for d in kb.list_diagnostics(db_connection, **filters)] == expected_ids


def test_search_looks_in_every_text_column(db_connection: Connection) -> None:
    found = kb.list_diagnostics(db_connection, search="PALLET")

    assert {26, 29, 30} <= {d.id for d in found}
    for d in found:
        texts = f"{d.symptom_description} {d.affected_component} {d.probable_cause} {d.recommended_solution}"
        assert "pallet" in texts.lower()


def test_gets_a_diagnostic_or_404(db_connection: Connection) -> None:
    assert kb.get_diagnostic(db_connection, 11).affected_component == "Pinza pneumatica end-effector"
    assert_http_error(lambda: kb.get_diagnostic(db_connection, 999), 404)


# --- Writing --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scope", "expected_names"),
    [
        ({}, (None, None)),
        ({"family_id": 3}, ("Cella di saldatura robotizzata", None)),
        ({"family_id": 3, "cycle_phase_id": 11}, ("Cella di saldatura robotizzata", "Saldatura")),
    ],
    ids=["generic", "family", "phase"],
)
def test_creates_a_diagnostic_in_every_scope(
    db_connection: Connection, scope: dict[str, int], expected_names: tuple[str | None, str | None]
) -> None:
    created = kb.create_diagnostic(db_connection, data(**scope), created_by=EXPERT_ID)

    assert created.id > 36
    assert created.created_by == EXPERT_ID
    assert (created.family_name, created.phase_name) == expected_names


@pytest.mark.parametrize(
    ("scope", "expected_status"),
    [({"family_id": 999}, 404), ({"family_id": 1, "cycle_phase_id": 999}, 404), ({"family_id": 1, "cycle_phase_id": 7}, 400)],
    ids=["unknown-family", "unknown-phase", "phase-of-another-family"],
)
def test_invalid_context_is_rejected_on_create_and_update(
    db_connection: Connection, scope: dict[str, int], expected_status: int
) -> None:
    assert_http_error(lambda: kb.create_diagnostic(db_connection, data(**scope), created_by=EXPERT_ID), expected_status)
    assert_http_error(lambda: kb.update_diagnostic(db_connection, 1, data(**scope)), expected_status)


def test_updates_a_diagnostic_and_its_scope(db_connection: Connection) -> None:
    updated = kb.update_diagnostic(db_connection, 30, data())

    assert (updated.id, updated.affected_component, updated.family_id, updated.cycle_phase_id) == (30, "Avvitatore elettrico", None, None)


def test_update_of_unknown_diagnostic_is_404_even_with_an_invalid_context(db_connection: Connection) -> None:
    assert_http_error(lambda: kb.update_diagnostic(db_connection, 999, data(family_id=999)), 404)


def test_deletes_a_diagnostic_or_404(db_connection: Connection) -> None:
    kb.delete_diagnostic(db_connection, 2)

    assert_http_error(lambda: kb.get_diagnostic(db_connection, 2), 404)
    assert_http_error(lambda: kb.delete_diagnostic(db_connection, 2), 404)


# --- CSV ------------------------------------------------------------------------------


def test_export_contains_every_diagnostic(db_connection: Connection) -> None:
    lines = kb.export_csv(db_connection).decode("utf-8-sig").strip().split("\r\n")

    assert lines[0].startswith("id;family_name;phase_number;phase_name;")
    assert len(lines) == 37
    assert lines[30].startswith("30;Cella di saldatura robotizzata;1;Ingresso pallet;")


def test_template_uses_a_real_family_and_phase(db_connection: Connection) -> None:
    lines = kb.template_csv(db_connection).decode("utf-8-sig").strip().split("\r\n")

    assert len(lines) == 4
    assert lines[1].startswith(";;;;Esempio")
    # Families are listed by name, so the first one is "Cella di assemblaggio robotizzata".
    assert lines[2].startswith(";Cella di assemblaggio robotizzata;;;Esempio")
    assert lines[3].startswith(";Cella di assemblaggio robotizzata;1;Carico pezzo;Esempio")
