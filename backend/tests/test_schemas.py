import pytest
from pydantic import ValidationError

from app.schemas.diagnosis import DiagnosisRequest
from app.schemas.knowledge_base import BaseDiagnosticIn, ExceptionIn


def test_diagnosis_request_strips_the_symptom() -> None:
    request = DiagnosisRequest(symptom="  la pinza non chiude  ", family_id=1, cycle_phase_id=2)

    assert request.symptom == "la pinza non chiude"


@pytest.mark.parametrize(
    "fields",
    [
        {"symptom": "   ", "family_id": 1, "cycle_phase_id": 1},
        {"symptom": "x" * 501, "family_id": 1, "cycle_phase_id": 1},
        {"symptom": "nastro fermo", "family_id": 0, "cycle_phase_id": 1},
        {"symptom": "nastro fermo", "family_id": 1, "cycle_phase_id": -3},
    ],
    ids=["blank-symptom", "symptom-too-long", "non-positive-family", "negative-phase"],
)
def test_invalid_diagnosis_requests_are_rejected(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DiagnosisRequest(**fields)


@pytest.mark.parametrize(
    ("field", "value"),
    [("symptom_description", " "), ("symptom_description", "x" * 501), ("affected_component", "x" * 151), ("probable_cause", "")],
)
def test_invalid_base_diagnostic_fields_are_rejected(field: str, value: str) -> None:
    valid = {
        "symptom_description": "Sintomo",
        "affected_component": "Componente",
        "probable_cause": "Causa",
        "recommended_solution": "Soluzione",
    }

    with pytest.raises(ValidationError):
        BaseDiagnosticIn(**{**valid, field: value})


def test_exception_requires_positive_ids_and_text() -> None:
    with pytest.raises(ValidationError):
        ExceptionIn(family_id=0, cycle_phase_id=1, specific_cause="c", specific_solution="s")
    with pytest.raises(ValidationError):
        ExceptionIn(family_id=1, cycle_phase_id=1, specific_cause="  ", specific_solution="s")
