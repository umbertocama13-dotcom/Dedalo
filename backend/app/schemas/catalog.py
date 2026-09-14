from pydantic import BaseModel


class FamilyOut(BaseModel):
    """A product family."""

    id: int
    family_name: str
    description: str | None


class PhaseOut(BaseModel):
    """A phase of a family's work cycle."""

    id: int
    family_id: int
    phase_number: int
    phase_name: str
