import httpx

from app.services.ai.base import AIProvider, AIProviderError, build_normalization_messages, clean_model_output


class LocalAIProvider(AIProvider):
    """Provider for a model served by Ollama on the company's own infrastructure."""

    def __init__(self, base_url: str, model: str, client: httpx.Client | None = None, timeout: float = 30.0) -> None:
        """Initializes the provider. No request is sent until normalize_symptom is called.

        Args:
            base_url: Ollama server URL, e.g. http://localhost:11434.
            model: Name of a model already pulled on the Ollama server.
            client: Optional HTTP client; tests inject one with a mock transport.
            timeout: Request timeout in seconds, used only when no client is given.
        """
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def normalize_symptom(self, text: str) -> str:
        """Asks the local model to rewrite the symptom.

        Args:
            text: Symptom as typed by the operator.

        Returns:
            The normalized symptom sentence.

        Raises:
            AIProviderError: If Ollama is unreachable, answers with an error or an unusable body.
        """
        payload = {
            "model": self._model,
            "messages": build_normalization_messages(text),
            # Without stream=False Ollama answers with one JSON object per generated token.
            "stream": False,
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
        return clean_model_output(content)
