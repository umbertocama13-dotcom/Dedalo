"""Types shared by every matcher and the Matcher interface.

The conversation service depends only on these types, so the matching engine
(semantic, fuzzy or a combination) can change without touching routes or repositories.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Scope = Literal["generic", "family", "phase"]

# Used to break score ties: a row written for the selected phase is more specific
# than one written for the whole family, which is more specific than a generic one.
SCOPE_SPECIFICITY: dict[Scope, int] = {"phase": 2, "family": 1, "generic": 0}


@dataclass(frozen=True)
class MatchCandidate:
    """A diagnostic that applies to the operator's context.

    Field names match the keys returned by
    ``diagnostics_repository.list_candidates``, so ``MatchCandidate(**row)`` works.
    """

    diagnostic_id: int
    symptom_description: str
    affected_component: str
    probable_cause: str
    recommended_solution: str
    family_id: int | None = None
    cycle_phase_id: int | None = None
    phase_number: int | None = None
    phase_name: str | None = None

    @property
    def scope(self) -> Scope:
        """Returns how specific the row is: generic, whole family or single phase."""
        if self.cycle_phase_id is not None:
            return "phase"
        if self.family_id is not None:
            return "family"
        return "generic"


@dataclass(frozen=True)
class MatchResult:
    """A candidate that passed the matcher, with its similarity score (0-1)."""

    candidate: MatchCandidate
    score: float


class Matcher(ABC):
    """Interface of a symptom matcher."""

    @abstractmethod
    def match(self, query: str, candidates: Sequence[MatchCandidate]) -> list[MatchResult]:
        """Returns the candidates that match the query, best first.

        Args:
            query: Free-text symptom typed by the operator.
            candidates: Diagnostics that apply to the operator's context.

        Returns:
            Matching results; an empty list means no match above the threshold.
        """


def sort_results(results: list[MatchResult]) -> list[MatchResult]:
    """Orders results so that the same input always gives the same order.

    Args:
        results: Unordered results.

    Returns:
        Results by score (highest first), then by scope specificity, then by diagnostic id.
    """
    return sorted(
        results,
        key=lambda result: (
            -result.score,
            -SCOPE_SPECIFICITY[result.candidate.scope],
            result.candidate.diagnostic_id,
        ),
    )
