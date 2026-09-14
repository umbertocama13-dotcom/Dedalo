"""Tests for the external OpenAI-compatible API provider.

The remote API is a paid third-party service, so it is replaced by httpx.MockTransport:
no request ever leaves the machine during tests.
"""

import json
from collections.abc import Callable

import httpx
import pytest

from app.services.ai.api_provider import ApiAIProvider
from app.services.ai.base import AIProviderError

SYMPTOM = "la pinza del robbot non si chiude bene"
API_KEY = "sk-test-secret-key"


def make_provider(
    handler: Callable[[httpx.Request], httpx.Response], api_url: str = "https://api.example.com/v1"
) -> ApiAIProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ApiAIProvider(api_url=api_url, api_key=API_KEY, model="test-model", client=client)


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]})


def test_sends_an_authenticated_deterministic_chat_completion_request() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return completion("La pinza del robot non chiude completamente")

    make_provider(handler).normalize_symptom(SYMPTOM)

    [request] = captured
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == "https://api.example.com/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == SYMPTOM


def test_trailing_slash_in_api_url_does_not_break_the_endpoint() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return completion("ok")

    make_provider(handler, api_url="https://api.example.com/v1/").normalize_symptom(SYMPTOM)

    assert str(captured[0].url) == "https://api.example.com/v1/chat/completions"


def test_returns_the_model_text_stripped() -> None:
    provider = make_provider(lambda request: completion("\n La pinza del robot non chiude completamente "))

    assert provider.normalize_symptom(SYMPTOM) == "La pinza del robot non chiude completamente"


def raise_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        raise_timeout,
        lambda request: httpx.Response(401, json={"error": {"message": "invalid api key"}}),
        lambda request: httpx.Response(429, json={"error": {"message": "rate limited"}}),
        lambda request: httpx.Response(200, text="<html>proxy error</html>"),
        lambda request: httpx.Response(200, json={"choices": []}),
        lambda request: completion(""),
        lambda request: completion("x" * 501),
    ],
    ids=["timeout", "http-401", "http-429", "not-json", "no-choices", "empty-output", "output-too-long"],
)
def test_failures_raise_ai_provider_error(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    with pytest.raises(AIProviderError):
        make_provider(handler).normalize_symptom(SYMPTOM)


def test_error_message_never_contains_the_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"bad key {request.headers['Authorization']}")

    with pytest.raises(AIProviderError) as error:
        make_provider(handler).normalize_symptom(SYMPTOM)

    assert API_KEY not in str(error.value)
