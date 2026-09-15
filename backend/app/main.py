import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.db import create_db_engine
from app.logging_config import configure_logging
from app.repositories import diagnostics_repository
from app.routes import auth, catalog, diagnosis, knowledge_base
from app.services.ai.factory import get_ai_provider
from app.services.embeddings.base import Embedder
from app.services.embeddings.embedding_cache import EmbeddingCache
from app.services.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder
from app.services.matching.semantic_matcher import SemanticMatcher

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, database_name: str | None = None, embedder: Embedder | None = None
) -> FastAPI:
    """Builds and configures the FastAPI application.

    Nothing happens at import time: logging, engine, AI provider, embedding model and
    matcher are created here, so tests can build isolated apps with their own settings.

    Args:
        settings: Settings to use; defaults to the ones read from the environment.
        database_name: Optional database override (the test suite uses the test DB).
        embedder: Embedding backend; defaults to the model in EMBEDDING_MODEL.
            Tests pass a lightweight fake instead of loading the model.

    Returns:
        The configured application.

    Raises:
        ValueError: If the AI provider configuration is invalid. It is checked before
            loading the embedding model, so a misconfiguration fails in a moment.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    ai_provider = get_ai_provider(settings)
    if embedder is None:
        embedder = SentenceTransformerEmbedder(
            settings.embedding_model, settings.embedding_query_prefix, settings.embedding_document_prefix
        )
    embedding_cache = EmbeddingCache(embedder)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _warm_up_embeddings(app)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Dedalo", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    # The engine connects lazily, so creating it here opens no connection yet.
    app.state.engine = create_db_engine(settings, database_name)
    app.state.embedding_cache = embedding_cache
    app.state.matcher = SemanticMatcher(
        embedding_cache,
        threshold=settings.semantic_recall_threshold,
        max_results=settings.max_candidates,
        use_fuzzy=settings.semantic_use_fuzzy,
    )
    app.state.ai_provider = ai_provider

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        # Lets the browser read the file name of the CSV downloads.
        expose_headers=["Content-Disposition"],
    )
    app.add_exception_handler(RequestValidationError, _validation_error_handler)

    for router in (auth.router, catalog.router, diagnosis.router, knowledge_base.router):
        app.include_router(router)

    return app


def _warm_up_embeddings(app: FastAPI) -> None:
    """Embeds every stored symptom at startup, so the first operator request is fast.

    A database error only logs a warning: the app still starts and texts are embedded
    on demand by the first requests.

    Args:
        app: Application whose engine and embedding cache are used.
    """
    try:
        with app.state.engine.connect() as connection:
            texts = diagnostics_repository.list_symptom_descriptions(connection)
    except SQLAlchemyError as error:
        logger.warning("Embedding warm-up skipped, database unavailable: %s", error)
        return
    app.state.embedding_cache.warm_up(texts)
    logger.info("Embedding cache warmed up with %d symptom texts", len(texts))


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
