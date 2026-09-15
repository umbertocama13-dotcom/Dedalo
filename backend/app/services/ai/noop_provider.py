from typing import Any

from app.services.ai.base import AIProvider, AIProviderError


class NoopAIProvider(AIProvider):
    """Provider used when AI_PROVIDER=none: the conversation stays deterministic and no text leaves the machine.

    A null object instead of None, so the rest of the application always receives an AIProvider.
    """

    enabled = False

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Always fails: callers are expected to check ``enabled`` first.

        Args:
            messages: Ignored.

        Raises:
            AIProviderError: Always.
        """
        raise AIProviderError("AI is disabled (AI_PROVIDER=none)")
