"""Diagnosis flow: validate context -> deterministic match -> optional AI fallback.

The AI provider never produces a diagnosis. It may only rewrite the operator's text,
and only when the original text finds nothing: a deterministic match is never replaced
by a model rewrite, and text leaves the machine only when strictly needed.
"""

import dataclasses
import logging
from typing import Literal

from sqlalchemy import Connection

from app.repositories import diagnostics_repository
from app.schemas.diagnosis import DiagnosisHypothesis, DiagnosisRequest, DiagnosisResponse
from app.services.ai.base import AIProvider, AIProviderError
from app.services.catalog_service import validate_family_phase
from app.services.matching.fuzzy_matcher import Matcher, MatchCandidate, MatchResult

logger = logging.getLogger(__name__)

MATCH_MESSAGE = "Diagnoses found in the knowledge base, ordered by similarity."
NO_MATCH_MESSAGE = (
    "No diagnosis in the knowledge base matches this symptom for the selected product family and cycle phase. "
    "No procedure is suggested: contact a specialized technician."
)


def diagnose(
    connection: Connection, request: DiagnosisRequest, matcher: Matcher, ai_provider: AIProvider
) -> DiagnosisResponse:
    """Finds the knowledge base entries matching a reported symptom.

    Args:
        connection: Open database connection.
        request: Symptom, product family and cycle phase selected by the operator.
        matcher: Matching engine (deterministic).
        ai_provider: Backend used to rewrite the text if the original finds no match.

    Returns:
        A "match" response with ordered hypotheses, or a "no_match" response
        that explicitly declares the absence of data.

    Raises:
        HTTPException: 404 if family or phase do not exist, 400 if the phase
            does not belong to the family.
    """
    validate_family_phase(connection, request.family_id, request.cycle_phase_id)

    rows = diagnostics_repository.list_match_candidates(connection, request.family_id, request.cycle_phase_id)
    candidates = [MatchCandidate(**row) for row in rows]

    results = matcher.match(request.symptom, candidates)
    if results:
        return _match_response(results, matched_on="original", matched_text=request.symptom)

    rewritten = _rewrite_with_ai(ai_provider, request.symptom)
    if rewritten is not None and rewritten != request.symptom:
        results = matcher.match(rewritten, candidates)
        if results:
            return _match_response(results, matched_on="ai_normalized", matched_text=rewritten)

    return DiagnosisResponse(status="no_match", message=NO_MATCH_MESSAGE)


def _rewrite_with_ai(ai_provider: AIProvider, text: str) -> str | None:
    """Asks the AI provider to rewrite the symptom, tolerating its failures.

    Args:
        ai_provider: Configured AI backend.
        text: Symptom as typed by the operator.

    Returns:
        The rewritten text, or None if the provider failed.
    """
    try:
        return ai_provider.normalize_symptom(text)
    except AIProviderError as error:
        # A missing or broken model must not block the deterministic answer.
        logger.warning("AI normalization unavailable, using deterministic matching only: %s", error)
        return None


def _match_response(
    results: list[MatchResult], matched_on: Literal["original", "ai_normalized"], matched_text: str
) -> DiagnosisResponse:
    """Builds a "match" response from matcher results.

    Args:
        results: Non-empty matcher results, already ordered.
        matched_on: Which text produced the match.
        matched_text: The text that produced the match.

    Returns:
        The response with one hypothesis per result.
    """
    return DiagnosisResponse(
        status="match",
        message=MATCH_MESSAGE,
        matched_on=matched_on,
        matched_text=matched_text,
        hypotheses=[DiagnosisHypothesis(**dataclasses.asdict(result)) for result in results],
    )
