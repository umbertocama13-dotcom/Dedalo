from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# TEXT columns hold 65,535 bytes; utf8mb4 uses up to 4 bytes per character.
MAX_TEXT_LENGTH = 10_000


class BaseDiagnosticIn(BaseModel):
    """Fields an expert provides to create or replace a base diagnostic."""

    model_config = ConfigDict(str_strip_whitespace=True)

    symptom_description: str = Field(min_length=1, max_length=500)
    affected_component: str = Field(min_length=1, max_length=150)
    probable_cause: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    recommended_solution: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


class BaseDiagnosticOut(BaseModel):
    """A base diagnostic as stored in the knowledge base."""

    id: int
    symptom_description: str
    affected_component: str
    probable_cause: str
    recommended_solution: str
    created_by: int
    created_at: datetime
    updated_at: datetime


class ExceptionIn(BaseModel):
    """Fields an expert provides to create or replace a context-specific exception."""

    model_config = ConfigDict(str_strip_whitespace=True)

    family_id: int = Field(gt=0)
    cycle_phase_id: int = Field(gt=0)
    specific_cause: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    specific_solution: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


class ExceptionOut(BaseModel):
    """A diagnostic exception as stored in the knowledge base."""

    id: int
    base_diagnostic_id: int
    family_id: int
    cycle_phase_id: int
    specific_cause: str
    specific_solution: str
    created_by: int
    created_at: datetime
    updated_at: datetime
