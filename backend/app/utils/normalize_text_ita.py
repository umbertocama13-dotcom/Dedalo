import re
import unicodedata

# Articles, simple and articulated prepositions, conjunctions and clitics that carry
# no meaning for matching. Elided forms ("dell'", "l'") appear without the apostrophe
# because punctuation is replaced by spaces before filtering.
# "non" is deliberately NOT a stopword: it reverses the meaning of a sentence.
ITALIAN_STOPWORDS: frozenset[str] = frozenset(
    {
        "il", "lo", "la", "i", "gli", "le", "l", "un", "uno", "una",
        "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
        "del", "dello", "della", "dei", "degli", "delle", "dell",
        "al", "allo", "alla", "ai", "agli", "alle", "all",
        "dal", "dallo", "dalla", "dai", "dagli", "dalle", "dall",
        "nel", "nello", "nella", "nei", "negli", "nelle", "nell",
        "sul", "sullo", "sulla", "sui", "sugli", "sulle", "sull",
        "col", "coi", "e", "ed", "o", "od", "ma", "che", "si", "ci", "ne",
    }
)

_NON_WORD_CHARS = re.compile(r"[^\w\s]")


def normalize_text_ita(text: str) -> str:
    """Normalizes Italian free text so that superficial differences do not affect comparisons.

    Steps: lowercase, accent removal, punctuation and symbols replaced by spaces,
    Italian stopwords removed, whitespace collapsed.

    Example:
        >>> normalize_text_ita("Il nastro si ferma, dell'aria è insufficiente!")
        'nastro ferma aria insufficiente'

    Args:
        text: Raw Italian text, e.g. a sentence typed by a user.

    Returns:
        The normalized text; an empty string if no meaningful word remains.
    """
    # NFKD splits accented letters into base letter + combining mark ("ù" -> "u" + "̀"),
    # so dropping the combining marks removes accents without a hand-written table.
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    words = _NON_WORD_CHARS.sub(" ", without_accents).split()
    return " ".join(word for word in words if word not in ITALIAN_STOPWORDS)
