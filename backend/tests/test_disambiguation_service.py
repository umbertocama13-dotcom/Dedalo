"""Unit tests for the deterministic choice question, without a database."""

from app.services.disambiguation_service import CHOICE_QUESTION, build_choice
from app.services.matching.base import MatchCandidate, MatchResult

GAP = 0.05


def result(diagnostic_id: int, symptom: str, score: float, component: str = "Componente") -> MatchResult:
    candidate = MatchCandidate(
        diagnostic_id=diagnostic_id,
        symptom_description=symptom,
        affected_component=component,
        probable_cause="Causa",
        recommended_solution="Soluzione",
    )
    return MatchResult(candidate=candidate, score=score)


def options(results: list[MatchResult], low_confidence: bool = False) -> list[tuple[str, list[int]]] | None:
    follow_up = build_choice(results, low_confidence=low_confidence, score_gap=GAP)
    if follow_up is None:
        return None
    assert (follow_up.type, follow_up.question) == ("choice", CHOICE_QUESTION)
    return [(option.label, option.diagnostic_ids) for option in follow_up.options]


def test_no_results_no_question() -> None:
    assert options([]) is None
    assert options([], low_confidence=True) is None


def test_clear_winner_needs_no_question() -> None:
    assert options([result(1, "A", 0.90), result(2, "B", 0.80)]) is None


def test_close_symptoms_become_options_grouped_by_symptom() -> None:
    # 4 is far below the best score, so it is not offered as an option.
    results = [result(1, "A", 0.80), result(2, "A", 0.79), result(3, "B", 0.78), result(4, "C", 0.60)]

    assert options(results) == [("A", [1, 2]), ("B", [3])]


def test_tied_rows_with_the_same_symptom_ask_for_the_component_even_if_others_follow() -> None:
    results = [
        result(26, "Cella in allarme", 1.0, component="Nastro pallet"),
        result(27, "Cella in allarme", 1.0, component="Barriera"),
        result(33, "Arco non si innesca", 0.57),
    ]

    assert options(results) == [("Nastro pallet", [26]), ("Barriera", [27])]


def test_gap_is_measured_from_the_first_different_symptom() -> None:
    # 2 has the same symptom as 1, so the relevant runner-up is 3, far enough below.
    results = [result(1, "A", 0.90), result(2, "A", 0.89), result(3, "B", 0.80)]

    assert options(results) is None


def test_gap_equal_to_the_threshold_despite_float_noise_needs_no_question() -> None:
    # 0.70 - 0.65 is 0.04999999999999993 in floating point.
    assert options([result(1, "A", 0.70), result(2, "B", 0.65)]) is None


def test_same_symptom_different_components_become_component_options() -> None:
    results = [
        result(26, "Cella in allarme", 0.72, component="Nastro pallet"),
        result(27, "Cella in allarme", 0.72, component="Barriera"),
        result(28, "Cella in allarme", 0.72, component="Torcia"),
    ]

    assert options(results) == [("Nastro pallet", [26]), ("Barriera", [27]), ("Torcia", [28])]


def test_same_symptom_and_component_cannot_be_told_apart() -> None:
    results = [result(1, "Nastro fermo", 0.80), result(2, "Nastro fermo", 0.80)]

    assert options(results) is None


def test_low_confidence_always_asks_even_with_a_clear_gap() -> None:
    assert options([result(1, "A", 0.60), result(2, "B", 0.51)], low_confidence=True) == [("A", [1]), ("B", [2])]


def test_low_confidence_single_group_asks_for_confirmation() -> None:
    results = [result(1, "Nastro fermo", 0.55), result(2, "Nastro fermo", 0.55)]

    assert options(results, low_confidence=True) == [("Nastro fermo", [1, 2])]
