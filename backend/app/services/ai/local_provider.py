from typing import Any

import httpx

from app.services.ai.base import AIProvider, AIProviderError, parse_json_object


class LocalAIProvider(AIProvider):
    """Provider for a model served by Ollama on the company's own infrastructure."""

    def __init__(self, base_url: str, model: str, client: httpx.Client | None = None, timeout: float = 30.0) -> None:
        """Initializes the provider. No request is sent until complete_json is called.

        Args:
            base_url: Ollama server URL, e.g. http://localhost:11434.
            model: Name of a model already pulled on the Ollama server.
            client: Optional HTTP client; tests inject one with a mock transport.
            timeout: Request timeout in seconds, used only when no client is given.
        """
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Sends the conversation to the local model in JSON mode.

        Args:
            messages: Chat messages with role and content.

        Returns:
            The JSON object produced by the model.

        Raises:
            AIProviderError: If Ollama is unreachable, answers with an error or an unusable body.
        """
        payload = {
            "model": self._model,
            "messages": messages,
            # Without stream=False Ollama answers with one JSON object per generated token.
            "stream": False,
            # Constrains generation to valid JSON.
            "format": "json",
            # Temperature 0 makes the output as repeatable as the model allows.
            "options": {"temperature": 0},
        }
        try:
            response = self._client.post(self._url, json=payload)
            response.raise_for_status()
            content = response.json()["message"]["content"]
        except httpx.HTTPStatusError as error:
            raise AIProviderError(f"Ollama answered with HTTP {error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise AIProviderError(f"Ollama request failed: {type(error).__name__}") from error
        except (ValueError, KeyError, TypeError) as error:
            raise AIProviderError("Ollama returned an unexpected response body") from error
        return parse_json_object(content)
