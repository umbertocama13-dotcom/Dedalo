"""Tests for the external OpenAI-compatible API provider.

The remote API is a paid third-party service, so it is replaced by httpx.MockTransport:
no request ever leaves the machine during tests.
"""

import json
from collections.abc import Callable

import httpx
import pytest

from app.services.ai.api_provider import ApiAIProvider
from app.services.ai.base import MAX_OUTPUT_LENGTH, AIProviderError

MESSAGES = [
    {"role": "system", "content": "istruzioni"},
    {"role": "user", "content": '{"candidates": [], "conversation": []}'},
]
API_KEY = "sk-test-secret-key"


def make_provider(
    handler: Callable[[httpx.Request], httpx.Response], api_url: str = "https://api.example.com/v1"
) -> ApiAIProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ApiAIProvider(api_url=api_url, api_key=API_KEY, model="test-model", client=client)


def completion(content: object) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]})


def test_sends_an_authenticated_deterministic_json_mode_request() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return completion('{"action": "no_match"}')

    make_provider(handler).complete_json(MESSAGES)

    [request] = captured
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == "https://api.example.com/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == MESSAGES


def test_trailing_slash_in_api_url_does_not_break_the_endpoint() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return completion("{}")

    make_provider(handler, api_url="https://api.example.com/v1/").complete_json(MESSAGES)

    assert str(captured[0].url) == "https://api.example.com/v1/chat/completions"


def test_returns_the_parsed_json_object() -> None:
    provider = make_provider(lambda request: completion('\n {"action": "ask", "question": "Il nastro è fermo?"} '))

    assert provider.complete_json(MESSAGES) == {"action": "ask", "question": "Il nastro è fermo?"}


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
        lambda request: completion(None),
        lambda request: completion(""),
        lambda request: completion("x" * (MAX_OUTPUT_LENGTH + 1)),
        lambda request: completion("Il nastro è fermo?"),
        lambda request: completion("[26, 27]"),
    ],
    ids=[
        "timeout",
        "http-401",
        "http-429",
        "body-not-json",
        "no-choices",
        "null-content",
        "empty-output",
        "output-too-long",
        "content-not-json",
        "content-not-an-object",
    ],
)
def test_failures_raise_ai_provider_error(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    with pytest.raises(AIProviderError):
        make_provider(handler).complete_json(MESSAGES)


def test_error_message_never_contains_the_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"bad key {request.headers['Authorization']}")

    with pytest.raises(AIProviderError) as error:
        make_provider(handler).complete_json(MESSAGES)

    assert API_KEY not in str(error.value)
