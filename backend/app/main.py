from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.db import create_db_engine
from app.logging_config import configure_logging
from app.routes import auth, catalog, diagnosis, knowledge_base
from app.services.ai.factory import get_ai_provider
from app.services.matching.fuzzy_matcher import FuzzyMatcher


def create_app(settings: Settings | None = None, database_name: str | None = None) -> FastAPI:
    """Builds and configures the FastAPI application.

    Nothing happens at import time: logging, engine, matcher and AI provider are
    created here, so tests can build isolated apps with their own settings.

    Args:
        settings: Settings to use; defaults to the ones read from the environment.
        database_name: Optional database override (the test suite uses the test DB).

    Returns:
        The configured application.

    Raises:
        ValueError: If the AI provider configuration is invalid (fail fast at startup).
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Dedalo", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    # The engine connects lazily, so creating it here opens no connection yet.
    app.state.engine = create_db_engine(settings, database_name)
    app.state.matcher = FuzzyMatcher(threshold=settings.match_score_threshold)
    app.state.ai_provider = get_ai_provider(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(RequestValidationError, _validation_error_handler)

    for router in (auth.router, catalog.router, diagnosis.router, knowledge_base.router):
        app.include_router(router)

    return app


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Returns 400 instead of FastAPI's default 422 for invalid input.

    Keeps the project-wide convention of one status code (400) for every invalid request.

    Args:
        request: The rejected request.
        exc: Validation error raised by FastAPI.

    Returns:
        A 400 response listing the validation errors.
    """
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": jsonable_encoder(exc.errors())})
