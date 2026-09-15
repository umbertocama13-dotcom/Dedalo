"""Optional LLM step of the conversation: ask the operator a question or narrow the hypotheses.

The model only sees hypotheses already retrieved from the database and may answer
with one of three actions. parse_decision rejects anything else, so an invented id,
a question when none is allowed or a malformed answer never reaches the operator.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from app.schemas.diagnosis import ChatMessage
from app.services.ai.base import AIProvider, AIProviderError
from app.services.matching.base import MatchResult

MAX_QUESTION_LENGTH = 300

SYSTEM_PROMPT = """You help a maintenance operator of an industrial production line to find the cause of a fault.
You receive the conversation with the operator and a list of candidate diagnoses taken from the company knowledge base.
Your only job is to choose among these candidates. Answer with exactly one JSON object, in one of these forms:

{"action": "ask", "question": "..."}
  Ask ONE short question in Italian about something the operator can observe on the machine,
  chosen so that the answer separates the candidates. Allowed only if questions_left is greater than 0.

{"action": "narrow", "diagnostic_ids": [..]}
  The conversation already shows which candidates fit: list their ids, most likely first.

{"action": "no_match"}
  None of the candidates fits what the operator describes.

Rules:
- Use only ids that appear in the candidates.
- Never invent causes, solutions, components or checks that are not in the candidates.
- Never state a cause or a solution inside the question.
- Do not ask about something the operator has already answered.
"""


class InvalidDecisionError(AIProviderError):
    """The model answered, but not with a valid decision."""


@dataclass(frozen=True)
class Decision:
    """A validated answer of the model."""

    action: Literal["ask", "narrow", "no_match"]
    question: str | None = None
    diagnostic_ids: tuple[int, ...] = ()


def decide(
    ai_provider: AIProvider,
    results: Sequence[MatchResult],
    conversation: Sequence[ChatMessage],
    questions_left: int,
    context_label: str,
) -> Decision:
    """Asks the model what to do next and validates the answer.

    Args:
        ai_provider: Enabled AI backend.
        results: Hypotheses retrieved by the matcher, best first.
        conversation: Whole conversation so far.
        questions_left: How many more questions the model may ask.
        context_label: Human-readable family and phase, e.g. "Cella di saldatura, fase non indicata".

    Returns:
        The validated decision.

    Raises:
        AIProviderError: If the backend fails or the answer is not a valid decision.
    """
    raw = ai_provider.complete_json(build_messages(results, conversation, questions_left, context_label))
    return parse_decision(raw, {result.candidate.diagnostic_id for result in results}, questions_left)


def build_messages(
    results: Sequence[MatchResult], conversation: Sequence[ChatMessage], questions_left: int, context_label: str
) -> list[dict[str, str]]:
    """Builds the chat messages sent to the model.

    Candidates and conversation travel as one JSON document in the user message, so
    operator text can never be mistaken for instructions of the system prompt.

    Args:
        results: Hypotheses retrieved by the matcher.
        conversation: Whole conversation so far.
        questions_left: How many more questions the model may ask.
        context_label: Human-readable family and phase.

    Returns:
        A system message and a user message.
    """
    payload = {
        "context": context_label,
        "questions_left": questions_left,
        "candidates": [
            {
                "id": result.candidate.diagnostic_id,
                "symptom": result.candidate.symptom_description,
                "component": result.candidate.affected_component,
                "phase": result.candidate.phase_name or "tutte le fasi",
                "cause": result.candidate.probable_cause,
                "solution": result.candidate.recommended_solution,
            }
            for result in results
        ],
        "conversation": [{"role": message.role, "content": message.content} for message in conversation],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def parse_decision(raw: dict[str, Any], candidate_ids: set[int], questions_left: int) -> Decision:
    """Validates the JSON object returned by the model.

    Args:
        raw: Parsed model answer.
        candidate_ids: Ids the model was allowed to use.
        questions_left: How many more questions the model may ask.

    Returns:
        The decision.

    Raises:
        InvalidDecisionError: If the action is unknown, a question is not allowed or
            malformed, or the ids are missing, malformed or not among the candidates.
    """
    action = raw.get("action")

    if action == "ask":
        if questions_left <= 0:
            raise InvalidDecisionError("model asked a question with no questions left")
        question = raw.get("question")
        if not isinstance(question, str) or not question.strip():
            raise InvalidDecisionError("model asked an empty question")
        if len(question.strip()) > MAX_QUESTION_LENGTH:
            raise InvalidDecisionError(f"model question longer than {MAX_QUESTION_LENGTH} characters")
        return Decision(action="ask", question=question.strip())

    if action == "narrow":
        ids = raw.get("diagnostic_ids")
        # bool is a subclass of int in Python: true/false must not pass as ids 1/0.
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            raise InvalidDecisionError("model returned malformed diagnostic ids")
        unknown = set(ids) - candidate_ids
        if unknown:
            raise InvalidDecisionError(f"model returned ids that are not candidates: {sorted(unknown)}")
        return Decision(action="narrow", diagnostic_ids=tuple(dict.fromkeys(ids)))

    if action == "no_match":
        return Decision(action="no_match")

    raise InvalidDecisionError("model returned an unknown action")
