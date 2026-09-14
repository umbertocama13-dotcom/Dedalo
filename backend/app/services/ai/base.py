"""Common interface for AI backends.

The rest of the application only depends on AIProvider: switching between external
API, local model or no AI at all is a configuration change (AI_PROVIDER in .env).

AI is only used to pre-process the operator's text. Diagnoses always come from the
database through the deterministic matcher, never from a model.
"""

from abc import ABC, abstractmethod

# Same limit as base_diagnostics.symptom_description (VARCHAR(500)): a longer output
# cannot be a symptom sentence and usually means the model ignored the instructions.
MAX_OUTPUT_LENGTH = 500

NORMALIZE_SYMPTOM_PROMPT = (
    "You normalize fault descriptions written by operators of an industrial production line. "
    "Rewrite the operator's text as one short symptom sentence in Italian: fix typos, remove "
    "filler words, keep every technical detail and any negation. "
    "Do NOT add causes, solutions or details that are not in the text. "
    "Reply with the sentence only."
)


class AIProviderError(Exception):
    """Raised when an AI backend is unreachable or returns an unusable answer.

    Messages never include request headers or raw response bodies, so secrets
    such as API keys cannot leak into logs.
    """


class AIProvider(ABC):
    """Interface implemented by every AI backend."""

    @abstractmethod
    def normalize_symptom(self, text: str) -> str:
        """Rewrites free operator text as a clean symptom description.

        Args:
            text: Symptom as typed by the operator.

        Returns:
            The normalized symptom sentence.

        Raises:
            AIProviderError: If the backend fails or its answer is unusable.
        """


def build_normalization_messages(text: str) -> list[dict[str, str]]:
    """Builds the chat messages shared by all chat-based backends.

    Args:
        text: Symptom as typed by the operator.

    Returns:
        A system message with the instructions and a user message with the text.
    """
    return [
        {"role": "system", "content": NORMALIZE_SYMPTOM_PROMPT},
        {"role": "user", "content": text},
    ]


def clean_model_output(content: object) -> str:
    """Validates and trims the text returned by a model.

    Args:
        content: Raw content extracted from the backend response.

    Returns:
        The trimmed text.

    Raises:
        AIProviderError: If the content is not a string, is empty or is too long.
    """
    if not isinstance(content, str):
        raise AIProviderError("model returned non-text content")
    cleaned = content.strip()
    if not cleaned:
        raise AIProviderError("model returned an empty answer")
    if len(cleaned) > MAX_OUTPUT_LENGTH:
        raise AIProviderError(f"model answer longer than {MAX_OUTPUT_LENGTH} characters")
    return cleaned
