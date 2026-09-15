from collections.abc import Sequence

from rapidfuzz import fuzz

from app.services.matching.base import Matcher, MatchCandidate, MatchResult, sort_results
from app.utils.normalize_text_ita import normalize_text_ita


def fuzzy_score(query: str, symptom: str) -> float:
    """String similarity of two Italian texts after normalization.

    token_sort_ratio compares the full sorted word lists: robust to typos and word
    order, but unlike token_set_ratio/WRatio it does not give a high score when the
    query shares only a subset of words with the symptom (e.g. "nastro" alone).
    The v1 scorer comparison is documented in workflow_sviluppo.md.

    Args:
        query: Text typed by the operator.
        symptom: Symptom description stored in the knowledge base.

    Returns:
        A score between 0 and 1.
    """
    return fuzz.token_sort_ratio(normalize_text_ita(query), normalize_text_ita(symptom)) / 100


class FuzzyMatcher(Matcher):
    """String-similarity matcher: the v1 engine.

    No longer used by the application, which relies on SemanticMatcher. It is kept as
    the baseline in scripts/evaluate_matching.py, so the v1 -> v2 improvement is measured
    on the same queries instead of being estimated.
    """

    def __init__(self, threshold: float = 0.8, max_results: int = 5) -> None:
        """Initializes the matcher.

        Args:
            threshold: Minimum similarity score (0-1) for a candidate to match.
            max_results: Maximum number of results.

        Raises:
            ValueError: If threshold is outside 0-1 or max_results is not positive.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between 0 and 1, got {threshold}")
        if max_results < 1:
            raise ValueError(f"max_results must be positive, got {max_results}")
        self.threshold = threshold
        self.max_results = max_results

    def match(self, query: str, candidates: Sequence[MatchCandidate]) -> list[MatchResult]:
        """Scores every candidate against the query and keeps those above the threshold.

        Args:
            query: Free-text symptom typed by the operator.
            candidates: Diagnostics that apply to the operator's context.

        Returns:
            Up to max_results results, ordered by score, scope specificity and id.
        """
        if not normalize_text_ita(query):
            return []
        results = []
        for candidate in candidates:
            score = round(fuzzy_score(query, candidate.symptom_description), 4)
            if score >= self.threshold:
                results.append(MatchResult(candidate=candidate, score=score))
        return sort_results(results)[: self.max_results]
