"""Relative probabilities of the hypotheses shown to the operator.

A cosine similarity of 0.62 does not mean "62% likely", and two close scores
(0.61 and 0.59) would not tell the operator which hypothesis to check first.
A softmax turns the scores into shares that sum to 100%.

"None of these" takes part in the softmax as one more candidate with a fixed score,
so a single weak hypothesis does not show 100%. Known limit: that share is only an
estimate calibrated on the fixture queries, not the real frequency of missing causes.
"""

import math
from collections.abc import Sequence


def relative_probabilities(scores: Sequence[float], temperature: float) -> list[float]:
    """Converts similarity scores into probabilities that sum to 1.

    Args:
        scores: Similarity scores of the hypotheses, any order.
        temperature: Softmax temperature. Lower values give more weight to the best
            score; it is calibrated on the fixture queries (see workflow_sviluppo.md).

    Returns:
        One probability per score, in the same order; empty if there are no scores.

    Raises:
        ValueError: If the temperature is not positive.
    """
    if temperature <= 0:
        raise ValueError(f"temperature must be positive, got {temperature}")
    if not scores:
        return []
    # Subtracting the maximum keeps every exponent <= 0, so exp() never overflows.
    best = max(scores)
    weights = [math.exp((score - best) / temperature) for score in scores]
    total = sum(weights)
    return [weight / total for weight in weights]


def probabilities_with_unknown(
    scores: Sequence[float], temperature: float, unknown_score: float
) -> tuple[list[int], int]:
    """Converts scores into whole percentages, keeping a share for "none of these".

    A hypothesis scoring well above ``unknown_score`` leaves "none of these" almost
    nothing; a weak one leaves it most of the probability.

    Args:
        scores: Similarity scores of the hypotheses.
        temperature: Softmax temperature.
        unknown_score: Score given to "none of these" (calibrated, see workflow_sviluppo.md).

    Returns:
        The percentage of each hypothesis, in the same order, and the percentage of
        "none of these". Together they sum to 100.
    """
    percentages = to_percentages(relative_probabilities([*scores, unknown_score], temperature))
    return percentages[:-1], percentages[-1]


def to_percentages(probabilities: Sequence[float]) -> list[int]:
    """Rounds probabilities to whole percentages that always sum to exactly 100.

    Plain rounding can give 99 or 101 (e.g. three equal shares give 33+33+33).
    The largest remainder method assigns the missing points to the shares that
    lost the most in the rounding, earlier positions first on ties.

    Args:
        probabilities: Probabilities summing to 1.

    Returns:
        Whole percentages in the same order; empty if there are no probabilities.
    """
    if not probabilities:
        return []
    raw = [probability * 100 for probability in probabilities]
    percentages = [math.floor(value) for value in raw]
    missing = 100 - sum(percentages)
    by_remainder = sorted(range(len(raw)), key=lambda index: (-(raw[index] - percentages[index]), index))
    for index in by_remainder[:missing]:
        percentages[index] += 1
    return percentages
