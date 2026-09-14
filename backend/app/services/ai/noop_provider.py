from app.services.ai.base import AIProvider


class NoopAIProvider(AIProvider):
    """Provider used when AI_PROVIDER=none: fully deterministic, no text leaves the machine."""

    def normalize_symptom(self, text: str) -> str:
        """Returns the text unchanged; the matcher's own normalization still applies.

        Args:
            text: Symptom as typed by the operator.

        Returns:
            The same text.
        """
        return text
