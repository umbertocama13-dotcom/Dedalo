from collections.abc import Sequence

from app.services.embeddings.embedding_cache import EmbeddingCache
from app.services.matching.base import Matcher, MatchCandidate, MatchResult, sort_results
from app.services.matching.fuzzy_matcher import fuzzy_score
from app.services.matching.negation_guard import contradicts
from app.utils.normalize_text_ita import normalize_text_ita


class SemanticMatcher(Matcher):
    """Matches by meaning: cosine similarity between sentence embeddings.

    Deterministic for a given model and knowledge base: no text is generated, the
    score only ranks rows that already exist in the database.
    """

    def __init__(
        self,
        cache: EmbeddingCache,
        threshold: float,
        max_results: int = 5,
        use_fuzzy: bool = False,
        negation_overlap: float = 85.0,
    ) -> None:
        """Initializes the matcher.

        Args:
            cache: Embedding cache wrapping the model.
            threshold: Minimum score (0-1) for a candidate to be returned.
            max_results: Maximum number of results.
            use_fuzzy: If True, the score is the higher of cosine similarity and
                rapidfuzz token_sort_ratio / 100, which helps with typos.
            negation_overlap: Overlap threshold of the negation guard (0-100).

        Raises:
            ValueError: If threshold is outside 0-1 or max_results is not positive.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between 0 and 1, got {threshold}")
        if max_results < 1:
            raise ValueError(f"max_results must be positive, got {max_results}")
        self._cache = cache
        self.threshold = threshold
        self.max_results = max_results
        self._use_fuzzy = use_fuzzy
        self._negation_overlap = negation_overlap

    def match(self, query: str, candidates: Sequence[MatchCandidate]) -> list[MatchResult]:
        """Scores every candidate and keeps the best ones above the threshold.

        Args:
            query: Free-text symptom typed by the operator.
            candidates: Diagnostics that apply to the operator's context.

        Returns:
            Up to max_results results, ordered by score, scope specificity and id.
        """
        normalized_query = normalize_text_ita(query)
        if not normalized_query or not candidates:
            return []

        query_vector = self._cache.query_vector(query)
        symptom_vectors = self._cache.document_vectors([candidate.symptom_description for candidate in candidates])
        # Vectors are unit length, so the dot product is the cosine similarity.
        similarities = symptom_vectors @ query_vector

        results = []
        for candidate, similarity in zip(candidates, similarities, strict=True):
            score = float(similarity)
            if self._use_fuzzy:
                score = max(score, fuzzy_score(query, candidate.symptom_description))
            # Rounded because float noise from parallel matrix math could swap two
            # equal scores between runs; clamped because rounding errors can exceed 1.
            score = round(min(score, 1.0), 4)
            if score < self.threshold:
                continue
            if contradicts(query, candidate.symptom_description, self._negation_overlap):
                continue
            results.append(MatchResult(candidate=candidate, score=score))

        return sort_results(results)[: self.max_results]
