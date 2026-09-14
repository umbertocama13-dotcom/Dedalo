"""Tests for the no-op and Ollama providers.

Ollama is an external process, so its HTTP API is replaced by httpx.MockTransport:
the provider code (request building, response parsing, error handling) runs for real.
"""

import json
from collections.abc import Callable

import httpx
import pytest

from app.services.ai.base import AIProviderError
from app.services.ai.local_provider import LocalAIProvider
from app.services.ai.noop_provider import NoopAIProvider

SYMPTOM = "il nastro trasportatre si ferma ogni tanto"


def make_provider(handler: Callable[[httpx.Request], httpx.Response]) -> LocalAIProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LocalAIProvider(base_url="http://ollama.test:11434", model="llama3.2", client=client)


def ollama_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}, "done": True})


def test_noop_provider_returns_text_unchanged() -> None:
    assert NoopAIProvider().normalize_symptom(SYMPTOM) == SYMPTOM


def test_local_provider_sends_a_deterministic_chat_request() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return ollama_reply("Il nastro trasportatore si ferma a intermittenza")

    make_provider(handler).normalize_symptom(SYMPTOM)

    [request] = captured
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == "http://ollama.test:11434/api/chat"
    assert body["model"] == "llama3.2"
    assert body["stream"] is False
    assert body["options"]["temperature"] == 0
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == SYMPTOM


def test_local_provider_returns_the_model_text_stripped() -> None:
    provider = make_provider(lambda request: ollama_reply("  Il nastro si ferma a intermittenza\n"))

    assert provider.normalize_symptom(SYMPTOM) == "Il nastro si ferma a intermittenza"


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
        lambda request: ollama_reply("x" * 501),
    ],
    ids=["unreachable", "http-500", "not-json", "unexpected-json", "empty-output", "output-too-long"],
)
def test_local_provider_failures_raise_ai_provider_error(
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    with pytest.raises(AIProviderError):
        make_provider(handler).normalize_symptom(SYMPTOM)
