from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz

from app.utils.normalize_text_ita import normalize_text_ita


@dataclass(frozen=True)
class MatchCandidate:
    """A base diagnostic, with its exception for the requested context if one exists.

    Field names match the keys returned by
    ``diagnostics_repository.list_match_candidates``, so ``MatchCandidate(**row)`` works.
    """

    base_diagnostic_id: int
    symptom_description: str
    affected_component: str
    probable_cause: str
    recommended_solution: str
    exception_id: int | None = None
    specific_cause: str | None = None
    specific_solution: str | None = None


@dataclass(frozen=True)
class MatchResult:
    """A candidate that passed the threshold, with the cause/solution to show.

    ``base_diagnostic_id`` always identifies the matched row, even when an
    exception replaced its cause and solution.
    """

    base_diagnostic_id: int
    exception_id: int | None
    symptom_description: str
    affected_component: str
    cause: str
    solution: str
    source: Literal["base", "exception"]
    score: float


class Matcher(ABC):
    """Interface of a symptom matcher.

    The diagnosis service depends only on this interface, so a future semantic
    matcher (e.g. local sentence-transformers) can replace or complement the fuzzy one.
    """

    @abstractmethod
    def match(self, query: str, candidates: Sequence[MatchCandidate]) -> list[MatchResult]:
        """Returns the candidates that match the query, best first.

        Args:
            query: Free-text symptom typed by the operator.
            candidates: Diagnostics available for the selected family and phase.

        Returns:
            Matching results; an empty list means no certain match.
        """


class FuzzyMatcher(Matcher):
    """Deterministic matcher based on string similarity of normalized symptoms."""

    def __init__(self, threshold: float = 80.0) -> None:
        """Initializes the matcher.

        Args:
            threshold: Minimum similarity score (0-100) for a candidate to match.

        Raises:
            ValueError: If the threshold is outside the 0-100 score range.
        """
        if not 0.0 <= threshold <= 100.0:
            raise ValueError(f"threshold must be between 0 and 100, got {threshold}")
        self.threshold = threshold

    def match(self, query: str, candidates: Sequence[MatchCandidate]) -> list[MatchResult]:
        """Scores every candidate against the query and keeps those above the threshold.

        Args:
            query: Free-text symptom typed by the operator.
            candidates: Diagnostics available for the selected family and phase.

        Returns:
            Results ordered by score (highest first), ties broken by diagnostic id
            so the order is always reproducible. Empty if nothing reaches the threshold.
        """
        normalized_query = normalize_text_ita(query)
        if not normalized_query:
            return []

        results = []
        for candidate in candidates:
            # token_sort_ratio compares the full sorted word lists: robust to typos and
            # word order, but unlike token_set_ratio/WRatio it does not give a high score
            # when the query shares only a subset of words with the symptom (e.g. "nastro"
            # alone, or same component with a different symptom). Scorer comparison on the
            # seed phrases is documented in workflow_sviluppo.md.
            score = fuzz.token_sort_ratio(normalized_query, normalize_text_ita(candidate.symptom_description))
            if score >= self.threshold:
                results.append(_build_result(candidate, score))

        return sorted(results, key=lambda result: (-result.score, result.base_diagnostic_id))


def _build_result(candidate: MatchCandidate, score: float) -> MatchResult:
    """Builds the result, letting a context exception replace cause and solution.

    Args:
        candidate: The matched candidate.
        score: Similarity score obtained by the candidate.

    Returns:
        The result with base or exception cause/solution.
    """
    has_exception = candidate.exception_id is not None
    return MatchResult(
        base_diagnostic_id=candidate.base_diagnostic_id,
        exception_id=candidate.exception_id,
        symptom_description=candidate.symptom_description,
        affected_component=candidate.affected_component,
        cause=candidate.specific_cause if has_exception else candidate.probable_cause,
        solution=candidate.specific_solution if has_exception else candidate.recommended_solution,
        source="exception" if has_exception else "base",
        score=score,
    )
