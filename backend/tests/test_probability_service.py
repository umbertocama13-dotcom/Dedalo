import pytest

from app.services.probability_service import probabilities_with_unknown, relative_probabilities, to_percentages


def test_probabilities_sum_to_one_and_follow_the_scores() -> None:
    probabilities = relative_probabilities([0.62, 0.81, 0.55], temperature=0.05)

    assert sum(probabilities) == pytest.approx(1.0)
    assert probabilities[1] > probabilities[0] > probabilities[2]


def test_equal_scores_get_equal_probabilities() -> None:
    assert relative_probabilities([0.7, 0.7], temperature=0.05) == pytest.approx([0.5, 0.5])


def test_single_and_empty_inputs() -> None:
    assert relative_probabilities([0.4], temperature=0.05) == [1.0]
    assert relative_probabilities([], temperature=0.05) == []


def test_lower_temperature_favours_the_best_score() -> None:
    soft = relative_probabilities([0.80, 0.75], temperature=0.20)
    sharp = relative_probabilities([0.80, 0.75], temperature=0.02)

    assert 0.5 < soft[0] < sharp[0] < 1.0


def test_extreme_values_do_not_overflow() -> None:
    probabilities = relative_probabilities([1000.0, 0.0], temperature=0.001)

    assert probabilities == pytest.approx([1.0, 0.0])


def test_a_weak_single_hypothesis_leaves_most_of_the_probability_to_none_of_these() -> None:
    assert probabilities_with_unknown([0.53], temperature=0.03, unknown_score=0.60) == ([9], 91)


def test_strong_hypotheses_leave_nothing_to_none_of_these() -> None:
    assert probabilities_with_unknown([1.0, 1.0], temperature=0.03, unknown_score=0.60) == ([50, 50], 0)


def test_without_hypotheses_none_of_these_is_everything() -> None:
    assert probabilities_with_unknown([], temperature=0.03, unknown_score=0.60) == ([], 100)


@pytest.mark.parametrize("temperature", [0.0, -0.1])
def test_non_positive_temperature_is_rejected(temperature: float) -> None:
    with pytest.raises(ValueError):
        relative_probabilities([0.5], temperature=temperature)


@pytest.mark.parametrize(
    ("probabilities", "expected"),
    [
        ([1 / 3, 1 / 3, 1 / 3], [34, 33, 33]),
        ([0.666, 0.334], [67, 33]),
        ([0.125, 0.125, 0.75], [13, 12, 75]),
        ([1.0], [100]),
        ([], []),
    ],
    ids=["three-equal", "two", "tie-on-remainder", "single", "empty"],
)
def test_percentages_always_sum_to_100(probabilities: list[float], expected: list[int]) -> None:
    percentages = to_percentages(probabilities)

    assert percentages == expected
    assert sum(percentages) in (0, 100)
