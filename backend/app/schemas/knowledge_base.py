from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Same limits as the diagnostics table columns.
MAX_SYMPTOM_LENGTH = 500
MAX_COMPONENT_LENGTH = 150
# TEXT columns hold 65,535 bytes; utf8mb4 uses up to 4 bytes per character.
MAX_TEXT_LENGTH = 10_000


class DiagnosticIn(BaseModel):
    """Fields an expert provides to create or replace a diagnostic.

    family_id and cycle_phase_id set the scope: both empty = every family,
    family only = whole family, family and phase = that phase only.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    symptom_description: str = Field(min_length=1, max_length=MAX_SYMPTOM_LENGTH)
    affected_component: str = Field(min_length=1, max_length=MAX_COMPONENT_LENGTH)
    probable_cause: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    recommended_solution: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    family_id: int | None = Field(default=None, gt=0)
    cycle_phase_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _phase_requires_family(self) -> Self:
        """Rejects a phase without its family, mirroring the database CHECK constraint."""
        if self.cycle_phase_id is not None and self.family_id is None:
            raise ValueError("cycle_phase_id requires family_id: a phase always belongs to a family")
        return self


class DiagnosticOut(BaseModel):
    """A diagnostic as stored in the knowledge base, with family and phase names."""

    id: int
    symptom_description: str
    affected_component: str
    probable_cause: str
    recommended_solution: str
    family_id: int | None
    family_name: str | None
    cycle_phase_id: int | None
    phase_number: int | None
    phase_name: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime


class ImportRowError(BaseModel):
    """A problem in an imported CSV file; the message is in Italian for the expert."""

    line: int
    column: str | None
    message: str


class ImportReport(BaseModel):
    """Outcome of a CSV import, both for the preview and for the real import."""

    applied: bool
    to_create: int
    to_update: int
    unchanged: int
    errors: list[ImportRowError]
