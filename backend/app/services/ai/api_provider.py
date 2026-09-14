import httpx

from app.services.ai.base import AIProvider, AIProviderError, build_normalization_messages, clean_model_output


class ApiAIProvider(AIProvider):
    """Provider for an external OpenAI-compatible chat completions API.

    Paid service: every call sends the operator's text outside the company network.
    Suitable for validating the PoC, not for production data.
    """

    def __init__(
        self, api_url: str, api_key: str, model: str, client: httpx.Client | None = None, timeout: float = 30.0
    ) -> None:
        """Initializes the provider. No request is sent until normalize_symptom is called.

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

    def normalize_symptom(self, text: str) -> str:
        """Asks the external model to rewrite the symptom.

        Args:
            text: Symptom as typed by the operator.

        Returns:
            The normalized symptom sentence.

        Raises:
            AIProviderError: If the API is unreachable, rejects the request or returns an unusable body.
        """
        payload = {
            "model": self._model,
            "messages": build_normalization_messages(text),
            # Temperature 0 makes the output as repeatable as the model allows.
            "temperature": 0,
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
        return clean_model_output(content)
