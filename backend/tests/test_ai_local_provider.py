"""Tests for the no-op and Ollama providers.

Ollama is an external process, so its HTTP API is replaced by httpx.MockTransport:
the provider code (request building, response parsing, error handling) runs for real.
"""

import json
from collections.abc import Callable

import httpx
import pytest

from app.services.ai.base import MAX_OUTPUT_LENGTH, AIProviderError
from app.services.ai.local_provider import LocalAIProvider
from app.services.ai.noop_provider import NoopAIProvider

MESSAGES = [{"role": "system", "content": "istruzioni"}, {"role": "user", "content": "{}"}]


def make_provider(handler: Callable[[httpx.Request], httpx.Response]) -> LocalAIProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LocalAIProvider(base_url="http://ollama.test:11434", model="llama3.2", client=client)


def ollama_reply(content: object) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}, "done": True})


def test_noop_provider_is_disabled_and_refuses_calls() -> None:
    provider = NoopAIProvider()

    assert provider.enabled is False
    with pytest.raises(AIProviderError):
        provider.complete_json(MESSAGES)


def test_real_providers_are_enabled() -> None:
    assert make_provider(lambda request: ollama_reply("{}")).enabled is True


def test_local_provider_sends_a_deterministic_json_request() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return ollama_reply('{"action": "no_match"}')

    make_provider(handler).complete_json(MESSAGES)

    [request] = captured
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == "http://ollama.test:11434/api/chat"
    assert body["model"] == "llama3.2"
    assert body["stream"] is False
    assert body["format"] == "json"
    assert body["options"]["temperature"] == 0
    assert body["messages"] == MESSAGES


def test_local_provider_returns_the_parsed_json_object() -> None:
    provider = make_provider(lambda request: ollama_reply('  {"action": "narrow", "diagnostic_ids": [1]}\n'))

    assert provider.complete_json(MESSAGES) == {"action": "narrow", "diagnostic_ids": [1]}


def raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        raise_connect_error,
        lambda request: httpx.Response(500, text="model crashed"),
        lambda request: httpx.Response(200, text="not json"),
        lambda request: httpx.Response(200, json={"unexpected": "shape"}),
        lambda request: ollama_reply("   "),
        lambda request: ollama_reply("x" * (MAX_OUTPUT_LENGTH + 1)),
        lambda request: ollama_reply("sì, certo"),
    ],
    ids=["unreachable", "http-500", "body-not-json", "unexpected-json", "empty-output", "output-too-long", "content-not-json"],
)
def test_local_provider_failures_raise_ai_provider_error(
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    with pytest.raises(AIProviderError):
        make_provider(handler).complete_json(MESSAGES)
