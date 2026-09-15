from typing import Any

import httpx

from app.services.ai.base import AIProvider, AIProviderError, parse_json_object


class ApiAIProvider(AIProvider):
    """Provider for an external OpenAI-compatible chat completions API.

    Paid service: every call sends the conversation outside the company network.
    Suitable for validating the PoC, not for production data.
    """

    def __init__(
        self, api_url: str, api_key: str, model: str, client: httpx.Client | None = None, timeout: float = 30.0
    ) -> None:
        """Initializes the provider. No request is sent until complete_json is called.

        Args:
            api_url: Base URL of the API, e.g. https://api.openai.com/v1.
            api_key: Secret API key, read from .env.
            model: Model name accepted by the API.
            client: Optional HTTP client; tests inject one with a mock transport.
            timeout: Request timeout in seconds, used only when no client is given.
        """
        self._url = f"{api_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Sends the conversation to the external model in JSON mode.

        Args:
            messages: Chat messages with role and content.

        Returns:
            The JSON object produced by the model.

        Raises:
            AIProviderError: If the API is unreachable, rejects the request or returns an unusable body.
        """
        payload = {
            "model": self._model,
            "messages": messages,
            # Temperature 0 makes the output as repeatable as the model allows.
            "temperature": 0,
            # JSON mode: the API guarantees syntactically valid JSON (the schema is still checked by us).
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._client.post(self._url, json=payload, headers=self._headers)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as error:
            # Only the status code: the response body may echo request data, including the key.
            raise AIProviderError(f"AI API answered with HTTP {error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise AIProviderError(f"AI API request failed: {type(error).__name__}") from error
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise AIProviderError("AI API returned an unexpected response body") from error
        return parse_json_object(content)
