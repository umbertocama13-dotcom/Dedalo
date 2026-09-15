"""Deterministic rule against matching a symptom with its opposite.

Embedding models give almost the same vector to "the gripper closes completely" and
"the gripper does not close completely": the negation is a single short word.
The rule only fires when the two sentences are nearly identical once negation words
are removed. A broader rule ("one side has 'non', the other does not") would also
discard correct paraphrases such as "la pinza chiude male" for
"la pinza non chiude completamente".
"""

from rapidfuzz import fuzz

from app.utils.normalize_text_ita import normalize_text_ita

# Words that reverse the meaning of an Italian sentence. Compared after normalization,
# so they are lowercase and without accents. "senza" is left out on purpose: it often
# describes a condition ("anche senza pezzo") rather than negating the symptom.
NEGATION_WORDS: frozenset[str] = frozenset({"non", "mai", "nessun", "nessuno", "nessuna", "niente", "nulla"})


def contradicts(query: str, symptom: str, overlap_threshold: float = 85.0) -> bool:
    """Tells whether the query describes the opposite of the symptom.

    Args:
        query: Text typed by the operator.
        symptom: Symptom description stored in the knowledge base.
        overlap_threshold: Minimum rapidfuzz token_sort_ratio (0-100) between the two
            sentences without negation words for them to count as the same sentence.

    Returns:
        True if exactly one of the texts is negated and the rest is nearly identical.
    """
    query_words = normalize_text_ita(query).split()
    symptom_words = normalize_text_ita(symptom).split()

    query_negated = any(word in NEGATION_WORDS for word in query_words)
    symptom_negated = any(word in NEGATION_WORDS for word in symptom_words)
    if query_negated == symptom_negated:
        return False

    query_core = " ".join(word for word in query_words if word not in NEGATION_WORDS)
    symptom_core = " ".join(word for word in symptom_words if word not in NEGATION_WORDS)
    if not query_core or not symptom_core:
        return False
    return fuzz.token_sort_ratio(query_core, symptom_core) >= overlap_threshold
