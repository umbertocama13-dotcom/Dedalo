from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DiagnosisRequest(BaseModel):
    """Symptom reported by an operator in a given family and cycle phase."""

    model_config = ConfigDict(str_strip_whitespace=True)

    symptom: str = Field(min_length=1, max_length=500)
    family_id: int = Field(gt=0)
    cycle_phase_id: int = Field(gt=0)


class DiagnosisHypothesis(BaseModel):
    """One knowledge base entry matching the symptom."""

    base_diagnostic_id: int
    exception_id: int | None
    symptom_description: str
    affected_component: str
    cause: str
    solution: str
    source: Literal["base", "exception"]
    score: float


class DiagnosisResponse(BaseModel):
    """Result of a diagnosis request.

    ``status`` is the field clients must branch on: new outcomes (e.g. a future
    "disambiguation" question) can be added as new values without breaking them.
    """

    status: Literal["match", "no_match"]
    message: str
    matched_on: Literal["original", "ai_normalized"] | None = None
    matched_text: str | None = None
    hypotheses: list[DiagnosisHypothesis] = Field(default_factory=list)
