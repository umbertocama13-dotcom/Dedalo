import pytest

from app.utils.normalize_text_ita import normalize_text_ita


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NASTRO   Trasportatore", "nastro trasportatore"),
        ("Saldatura irregolare, con grinze!", "saldatura irregolare grinze"),
        ("Temperatura più alta di 5 °C", "temperatura piu alta 5 c"),
        ("Pressione dell'aria insufficiente", "pressione aria insufficiente"),
        ("Il nastro si ferma a intermittenza", "nastro ferma intermittenza"),
    ],
    ids=["case-and-spaces", "punctuation", "accents-and-symbols", "apostrophe-elision", "stopwords"],
)
def test_normalize_text_ita(raw: str, expected: str) -> None:
    assert normalize_text_ita(raw) == expected


def test_negation_is_kept() -> None:
    # "non" reverses the meaning of a symptom, so it must survive stopword removal.
    assert normalize_text_ita("La pinza non chiude") == "pinza non chiude"


@pytest.mark.parametrize("raw", ["", "   ", "il la di, e!"])
def test_text_without_meaningful_words_becomes_empty(raw: str) -> None:
    assert normalize_text_ita(raw) == ""
