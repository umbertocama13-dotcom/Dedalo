import logging

from app.config import Settings
from app.services.ai.api_provider import ApiAIProvider
from app.services.ai.base import AIProvider
from app.services.ai.local_provider import LocalAIProvider
from app.services.ai.noop_provider import NoopAIProvider

logger = logging.getLogger(__name__)


def get_ai_provider(settings: Settings) -> AIProvider:
    """Instantiates the AI backend selected by AI_PROVIDER.

    Meant to be called once at application startup, so a misconfiguration stops
    the app immediately instead of failing on the first operator request.

    Args:
        settings: Application settings.

    Returns:
        The configured provider, always typed as the AIProvider interface.

    Raises:
        ValueError: If AI_PROVIDER is unknown or its required settings are empty.
    """
    if settings.ai_provider == "none":
        return NoopAIProvider()

    if settings.ai_provider == "api":
        _require(settings, "ai_api_url", "ai_api_key", "ai_api_model")
        logger.warning("AI_PROVIDER=api: operator text will be sent to %s, outside the company network", settings.ai_api_url)
        return ApiAIProvider(api_url=settings.ai_api_url, api_key=settings.ai_api_key, model=settings.ai_api_model)

    if settings.ai_provider == "local":
        _require(settings, "ollama_base_url", "ollama_model")
        return LocalAIProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)

    raise ValueError(f"Unknown AI_PROVIDER '{settings.ai_provider}': expected none, api or local")


def _require(settings: Settings, *field_names: str) -> None:
    """Checks that the settings needed by the selected provider are not empty.

    Args:
        settings: Application settings.
        *field_names: Settings attribute names that must be non-empty.

    Raises:
        ValueError: Listing the missing variables with their .env names.
    """
    missing = [name.upper() for name in field_names if not getattr(settings, name)]
    if missing:
        raise ValueError(f"AI_PROVIDER={settings.ai_provider} requires these variables in .env: {', '.join(missing)}")
