from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_MESSAGE_LENGTH = 1000
MAX_MESSAGES = 20
MAX_EXCLUDED_IDS = 100


class ChatMessage(BaseModel):
    """A message of the diagnosis conversation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["operator", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class DiagnosisRequest(BaseModel):
    """One turn of the diagnosis conversation.

    The server keeps no conversation state: the client sends the whole history and
    the hypotheses the operator already excluded at every turn.
    """

    family_id: int = Field(gt=0)
    cycle_phase_id: int | None = Field(default=None, gt=0)
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    excluded_diagnostic_ids: list[int] = Field(default_factory=list, max_length=MAX_EXCLUDED_IDS)

    @model_validator(mode="after")
    def _needs_operator_text(self) -> Self:
        """Rejects a conversation without any message from the operator."""
        if not any(message.role == "operator" for message in self.messages):
            raise ValueError("messages must contain at least one operator message")
        return self


class Hypothesis(BaseModel):
    """A knowledge base entry compatible with the symptom. Every text comes from the database."""

    diagnostic_id: int
    symptom_description: str
    affected_component: str
    cause: str
    solution: str
    scope: Literal["generic", "family", "phase"]
    phase_number: int | None
    phase_name: str | None
    score: float
    probability: int = Field(ge=0, le=100, description="Estimated probability relative to the other hypotheses (%)")


class ChoiceOption(BaseModel):
    """An answer to a choice question: picking it excludes the ids of every other option."""

    label: str
    diagnostic_ids: list[int]


class FollowUp(BaseModel):
    """Question that helps narrowing the hypotheses: a fixed choice or a model-written question."""

    type: Literal["choice", "question"]
    question: str
    options: list[ChoiceOption] = Field(default_factory=list)


class DiagnosisResponse(BaseModel):
    """Result of a conversation turn.

    ``status`` is the field clients must branch on. With "hypotheses", ``confidence``
    tells whether the best hypothesis passed the match threshold ("high") or only the
    lower recall threshold ("low").
    """

    status: Literal["hypotheses", "no_match"]
    confidence: Literal["high", "low"] | None = None
    mode: Literal["deterministic", "llm"]
    ai_fallback: bool = Field(default=False, description="True if the AI was enabled but could not be used")
    message: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    unknown_probability: int | None = Field(
        default=None, ge=0, le=100, description="Estimated probability that the cause is none of the hypotheses (%)"
    )
    follow_up: FollowUp | None = None
