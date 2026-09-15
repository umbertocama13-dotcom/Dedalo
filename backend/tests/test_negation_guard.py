import pytest

from app.services.matching.negation_guard import contradicts

GRIPPER = "La pinza del robot non chiude completamente"


@pytest.mark.parametrize(
    ("query", "symptom"),
    [
        ("La pinza del robot chiude completamente", GRIPPER),
        ("Il sensore induttivo rileva la presenza del pezzo", "Il sensore induttivo non rileva la presenza del pezzo"),
        ("Nessun segnale dal sensore di ingresso", "Segnale dal sensore di ingresso"),
        ("il robot NON preleva il pezzo dal nastro!", "Il robot preleva il pezzo dal nastro"),
    ],
    ids=["query-affirmative", "sensor", "nessun", "case-and-punctuation"],
)
def test_same_sentence_with_opposite_negation_contradicts(query: str, symptom: str) -> None:
    assert contradicts(query, symptom)


@pytest.mark.parametrize(
    ("query", "symptom"),
    [
        ("la pinza del robot non si chiude completamente", GRIPPER),
        ("la pinza chiude male", GRIPPER),
        ("staffe chiuse ma il robot resta fermo", "Gli staffaggi bloccano il pezzo ma il robot non parte"),
        ("il motore fa fumo", GRIPPER),
        ("non", GRIPPER),
        ("", GRIPPER),
    ],
    ids=["both-negated", "paraphrase", "different-wording", "unrelated", "only-negation", "empty"],
)
def test_other_pairs_do_not_contradict(query: str, symptom: str) -> None:
    assert not contradicts(query, symptom)


def test_overlap_threshold_is_configurable() -> None:
    query = "La pinza chiude completamente"

    assert contradicts(query, GRIPPER, overlap_threshold=70.0)
    assert not contradicts(query, GRIPPER, overlap_threshold=100.0)
