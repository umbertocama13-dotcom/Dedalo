"""Deterministic choice question, used when the hypotheses cannot be ranked with confidence.

Options come from the knowledge base itself (symptom texts, or components when the
symptom is the same), so no expert has to write questions in advance and no text is generated.
"""

from collections.abc import Callable, Sequence

from app.schemas.diagnosis import ChoiceOption, FollowUp
from app.services.matching.base import MatchResult

CHOICE_QUESTION = "Quale di queste descrive meglio la situazione?"


def build_choice(results: Sequence[MatchResult], low_confidence: bool, score_gap: float) -> FollowUp | None:
    """Builds a choice question, or returns None when the ranking is already clear.

    The question is about the hypotheses still "in the race": those scoring within
    ``score_gap`` of the best one, or all of them when the best one is uncertain.
    Options group them by symptom when symptoms differ, otherwise by component (same
    symptom caused by different components, e.g. a whole cell stopping). Rows with the
    same symptom and component cannot be told apart by the operator: no question, they
    are checked in order of probability.

    Args:
        results: Hypotheses ordered by score.
        low_confidence: True if the best score is below the match threshold.
        score_gap: Maximum score distance for two hypotheses to count as tied.

    Returns:
        The question with one option per group of contending hypotheses, or None.
    """
    if not results:
        return None

    if low_confidence:
        contenders = list(results)
    else:
        # Rounded because scores are rounded to 4 decimals and 0.70 - 0.65 is 0.04999... in floating point.
        contenders = [result for result in results if round(results[0].score - result.score, 4) < score_gap]

    key = _grouping_key(contenders)
    if key is None:
        if not low_confidence:
            return None
        # A single group: the question becomes a confirmation ("this one" or "none of these").
        key = _symptom

    groups: dict[str, list[int]] = {}
    for result in contenders:
        groups.setdefault(key(result), []).append(result.candidate.diagnostic_id)
    return FollowUp(
        type="choice",
        question=CHOICE_QUESTION,
        options=[ChoiceOption(label=label, diagnostic_ids=ids) for label, ids in groups.items()],
    )


def _grouping_key(results: Sequence[MatchResult]) -> Callable[[MatchResult], str] | None:
    """Chooses what distinguishes the hypotheses for the operator.

    Args:
        results: Hypotheses to group.

    Returns:
        The symptom text if symptoms differ, else the component if components differ,
        else None (every hypothesis has the same symptom and component).
    """
    if len({_symptom(result) for result in results}) > 1:
        return _symptom
    if len({_component(result) for result in results}) > 1:
        return _component
    return None


def _symptom(result: MatchResult) -> str:
    return result.candidate.symptom_description


def _component(result: MatchResult) -> str:
    return result.candidate.affected_component
