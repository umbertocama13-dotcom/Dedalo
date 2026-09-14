import pytest

from app.config import Settings
from app.services.ai.api_provider import ApiAIProvider
from app.services.ai.base import AIProvider
from app.services.ai.factory import get_ai_provider
from app.services.ai.local_provider import LocalAIProvider
from app.services.ai.noop_provider import NoopAIProvider


@pytest.fixture
def base_settings(settings: Settings) -> Settings:
    # Start from a known AI configuration, independent of the developer's .env.
    return settings.model_copy(
        update={
            "ai_provider": "none",
            "ai_api_url": "",
            "ai_api_key": "",
            "ai_api_model": "",
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "",
        }
    )


def test_none_returns_the_deterministic_noop_provider(base_settings: Settings) -> None:
    provider = get_ai_provider(base_settings)

    assert isinstance(provider, NoopAIProvider)
    assert isinstance(provider, AIProvider)


def test_local_returns_the_ollama_provider(base_settings: Settings) -> None:
    settings = base_settings.model_copy(update={"ai_provider": "local", "ollama_model": "llama3.2"})

    assert isinstance(get_ai_provider(settings), LocalAIProvider)


def test_api_returns_the_external_api_provider(base_settings: Settings) -> None:
    settings = base_settings.model_copy(
        update={
            "ai_provider": "api",
            "ai_api_url": "https://api.example.com",
            "ai_api_key": "test-key",
            "ai_api_model": "test-model",
        }
    )

    assert isinstance(get_ai_provider(settings), ApiAIProvider)


@pytest.mark.parametrize(
    "missing",
    ["ai_api_url", "ai_api_key", "ai_api_model"],
)
def test_api_without_required_setting_fails_at_startup(base_settings: Settings, missing: str) -> None:
    complete = {
        "ai_provider": "api",
        "ai_api_url": "https://api.example.com",
        "ai_api_key": "test-key",
        "ai_api_model": "test-model",
    }
    settings = base_settings.model_copy(update={**complete, missing: ""})

    with pytest.raises(ValueError, match=missing.upper()):
        get_ai_provider(settings)


def test_local_without_model_fails_at_startup(base_settings: Settings) -> None:
    settings = base_settings.model_copy(update={"ai_provider": "local"})

    with pytest.raises(ValueError, match="OLLAMA_MODEL"):
        get_ai_provider(settings)


def test_unknown_provider_is_rejected(base_settings: Settings) -> None:
    # model_copy skips validation, so this reproduces a value the Literal type would normally block.
    settings = base_settings.model_copy(update={"ai_provider": "cloud"})

    with pytest.raises(ValueError, match="cloud"):
        get_ai_provider(settings)
