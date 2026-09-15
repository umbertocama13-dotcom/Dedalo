"""Diagnosis conversation: context -> semantic retrieval -> hypotheses with probabilities -> follow-up.

Cause and solution always come from the database. When enabled, the LLM can only ask
a question or narrow the retrieved hypotheses; if it fails or answers with something
invalid, the deterministic flow answers instead.
"""

import logging
from collections.abc import Sequence
from typing import Literal

from sqlalchemy import Connection

from app.config import Settings
from app.repositories import catalog_repository, diagnostics_repository
from app.schemas.diagnosis import DiagnosisRequest, DiagnosisResponse, FollowUp, Hypothesis
from app.services import llm_advisor_service
from app.services.ai.base import AIProvider, AIProviderError
from app.services.catalog_service import validate_family_phase
from app.services.disambiguation_service import build_choice
from app.services.matching.base import Matcher, MatchCandidate, MatchResult, sort_results
from app.services.probability_service import probabilities_with_unknown

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_MESSAGE = "Hypotheses found in the knowledge base, ordered by estimated probability."
LOW_CONFIDENCE_MESSAGE = (
    "No hypothesis matches the symptom with certainty: verify them carefully or describe the symptom in more detail."
)
NO_MATCH_MESSAGE = (
    "No diagnosis in the knowledge base matches this symptom for the selected context. "
    "No procedure is suggested: contact a specialized technician."
)


def diagnose(
    connection: Connection,
    request: DiagnosisRequest,
    matcher: Matcher,
    ai_provider: AIProvider,
    settings: Settings,
) -> DiagnosisResponse:
    """Answers one turn of the diagnosis conversation.

    Args:
        connection: Open database connection.
        request: Context, conversation and hypotheses excluded by the operator.
        matcher: Matching engine (deterministic).
        ai_provider: AI backend; with ``enabled`` False the flow is fully deterministic.
        settings: Thresholds, temperature and limits of the conversation.

    Returns:
        The hypotheses with their probabilities and an optional follow-up question,
        or "no_match" when nothing in the knowledge base fits.

    Raises:
        HTTPException: 404 if family or phase do not exist, 400 if the phase does
            not belong to the family.
    """
    validate_family_phase(connection, request.family_id, request.cycle_phase_id)

    excluded = set(request.excluded_diagnostic_ids)
    candidates = [
        MatchCandidate(**row)
        for row in diagnostics_repository.list_candidates(connection, request.family_id, request.cycle_phase_id)
        if row["diagnostic_id"] not in excluded
    ]
    operator_texts = [message.content for message in request.messages if message.role == "operator"]
    results = _retrieve(matcher, operator_texts, candidates, settings.max_candidates)
    if not results:
        return DiagnosisResponse(status="no_match", mode="deterministic", message=NO_MATCH_MESSAGE)

    if not ai_provider.enabled:
        return _deterministic_response(results, settings, ai_fallback=False)

    questions_asked = sum(1 for message in request.messages if message.role == "assistant")
    try:
        decision = llm_advisor_service.decide(
            ai_provider,
            results,
            request.messages,
            questions_left=max(settings.max_llm_questions - questions_asked, 0),
            context_label=_context_label(connection, request),
        )
    except AIProviderError as error:
        # A missing, slow or misbehaving model must not block the deterministic answer.
        logger.warning("LLM step unavailable, answering deterministically: %s", error)
        return _deterministic_response(results, settings, ai_fallback=True)
    return _llm_response(decision, results, settings)


def _retrieve(
    matcher: Matcher, texts: Sequence[str], candidates: Sequence[MatchCandidate], limit: int
) -> list[MatchResult]:
    """Matches every operator message and keeps the best score of each diagnostic.

    Later messages are often answers ("sì, dopo il cambio formato") that match nothing
    on their own: taking the best score per diagnostic keeps the first description relevant.

    Args:
        matcher: Matching engine.
        texts: Operator messages, oldest first.
        candidates: Diagnostics of the context, minus the excluded ones.
        limit: Maximum number of hypotheses.

    Returns:
        The best results, ordered.
    """
    best: dict[int, MatchResult] = {}
    for text in texts:
        for result in matcher.match(text, candidates):
            current = best.get(result.candidate.diagnostic_id)
            if current is None or result.score > current.score:
                best[result.candidate.diagnostic_id] = result
    return sort_results(list(best.values()))[:limit]


def _deterministic_response(results: list[MatchResult], settings: Settings, ai_fallback: bool) -> DiagnosisResponse:
    """Builds the answer without any model: hypotheses plus an optional choice question.

    Args:
        results: Non-empty ordered results.
        settings: Conversation settings.
        ai_fallback: True if the AI was enabled but could not be used.

    Returns:
        The response.
    """
    confidence = _confidence(results, settings)
    hypotheses, unknown_probability = _hypotheses(results, settings)
    return DiagnosisResponse(
        status="hypotheses",
        confidence=confidence,
        mode="deterministic",
        ai_fallback=ai_fallback,
        message=HIGH_CONFIDENCE_MESSAGE if confidence == "high" else LOW_CONFIDENCE_MESSAGE,
        hypotheses=hypotheses,
        unknown_probability=unknown_probability,
        follow_up=build_choice(results, low_confidence=confidence == "low", score_gap=settings.disambiguation_score_gap),
    )


def _llm_response(
    decision: llm_advisor_service.Decision, results: list[MatchResult], settings: Settings
) -> DiagnosisResponse:
    """Applies a validated model decision to the retrieved hypotheses.

    The model decides which hypotheses stay, never their order or probability:
    both are always computed from the similarity scores.

    Args:
        decision: Validated decision.
        results: Non-empty ordered results.
        settings: Conversation settings.

    Returns:
        The response.
    """
    if decision.action == "no_match":
        return DiagnosisResponse(status="no_match", mode="llm", message=NO_MATCH_MESSAGE)

    follow_up = None
    kept = results
    if decision.action == "narrow":
        kept = [result for result in results if result.candidate.diagnostic_id in decision.diagnostic_ids]
    else:
        follow_up = FollowUp(type="question", question=decision.question)

    confidence = _confidence(kept, settings)
    hypotheses, unknown_probability = _hypotheses(kept, settings)
    return DiagnosisResponse(
        status="hypotheses",
        confidence=confidence,
        mode="llm",
        message=HIGH_CONFIDENCE_MESSAGE if confidence == "high" else LOW_CONFIDENCE_MESSAGE,
        hypotheses=hypotheses,
        unknown_probability=unknown_probability,
        follow_up=follow_up,
    )


def _confidence(results: list[MatchResult], settings: Settings) -> Literal["high", "low"]:
    """Returns "high" if the best score reaches the match threshold, else "low"."""
    return "high" if results[0].score >= settings.semantic_match_threshold else "low"


def _hypotheses(results: list[MatchResult], settings: Settings) -> tuple[list[Hypothesis], int]:
    """Converts results into hypotheses with whole percentages.

    Args:
        results: Non-empty ordered results.
        settings: Settings with the softmax temperature and the "none of these" score.

    Returns:
        The hypotheses, in the same order, and the percentage of "none of these";
        all percentages sum to 100.
    """
    percentages, unknown_probability = probabilities_with_unknown(
        [result.score for result in results], settings.probability_temperature, settings.probability_unknown_score
    )
    hypotheses = [
        Hypothesis(
            diagnostic_id=result.candidate.diagnostic_id,
            symptom_description=result.candidate.symptom_description,
            affected_component=result.candidate.affected_component,
            cause=result.candidate.probable_cause,
            solution=result.candidate.recommended_solution,
            scope=result.candidate.scope,
            phase_number=result.candidate.phase_number,
            phase_name=result.candidate.phase_name,
            score=result.score,
            probability=percentage,
        )
        for result, percentage in zip(results, percentages, strict=True)
    ]
    return hypotheses, unknown_probability


def _context_label(connection: Connection, request: DiagnosisRequest) -> str:
    """Describes family and phase for the model prompt.

    Args:
        connection: Open database connection.
        request: Request with an already validated context.

    Returns:
        E.g. "Cella di saldatura robotizzata, fase 1 Ingresso pallet".
    """
    family = catalog_repository.get_family(connection, request.family_id)
    if request.cycle_phase_id is None:
        return f"{family['family_name']}, fase non indicata"
    phase = catalog_repository.get_phase(connection, request.cycle_phase_id)
    return f"{family['family_name']}, fase {phase['phase_number']} {phase['phase_name']}"
