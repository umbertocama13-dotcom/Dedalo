"""Common interface for AI backends.

The rest of the application only depends on AIProvider: switching between external
API, local model or no AI at all is a configuration change (AI_PROVIDER in .env).

A model never produces a diagnosis. It can only ask the operator a question or narrow
the candidates already retrieved from the database, and the conversation service
validates every answer before using it.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

# A question plus a list of ids fits in a few hundred characters: a much longer
# answer usually means the model ignored the instructions.
MAX_OUTPUT_LENGTH = 2000


class AIProviderError(Exception):
    """Raised when an AI backend is unreachable, disabled or returns an unusable answer.

    Messages never include request headers or raw response bodies, so secrets
    such as API keys cannot leak into logs.
    """


class AIProvider(ABC):
    """Interface implemented by every AI backend."""

    # False only for the no-op backend: the conversation then skips the model entirely.
    enabled: bool = True

    @abstractmethod
    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Sends a chat conversation and returns the model answer as a JSON object.

        Args:
            messages: Chat messages with "role" (system, user, assistant) and "content".

        Returns:
            The JSON object produced by the model, not yet validated against a schema.

        Raises:
            AIProviderError: If the backend fails, is disabled or its answer is not a JSON object.
        """


def parse_json_object(content: object) -> dict[str, Any]:
    """Validates the text returned by a model and parses it as a JSON object.

    Args:
        content: Raw content extracted from the backend response.

    Returns:
        The parsed object.

    Raises:
        AIProviderError: If the content is not text, is empty, too long, not JSON or not an object.
    """
    if not isinstance(content, str):
        raise AIProviderError("model returned non-text content")
    cleaned = content.strip()
    if not cleaned:
        raise AIProviderError("model returned an empty answer")
    if len(cleaned) > MAX_OUTPUT_LENGTH:
        raise AIProviderError(f"model answer longer than {MAX_OUTPUT_LENGTH} characters")
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise AIProviderError("model answer is not valid JSON") from error
    if not isinstance(value, dict):
        raise AIProviderError("model answer is not a JSON object")
    return value
