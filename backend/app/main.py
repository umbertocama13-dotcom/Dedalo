import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.db import create_db_engine
from app.logging_config import configure_logging
from app.repositories import diagnostics_repository
from app.routes import auth, catalog, diagnosis, knowledge_base, setup, users
from app.services.ai.factory import get_ai_provider
from app.services.embeddings.base import Embedder
from app.services.embeddings.embedding_cache import EmbeddingCache
from app.services.embeddings.factory import create_embedder
from app.services.matching.semantic_matcher import SemanticMatcher

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    database_name: str | None = None,
    embedder: Embedder | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Builds and configures the FastAPI application.

    Nothing happens at import time: logging, engine, AI provider, embedding model and
    matcher are created here, so tests can build isolated apps with their own settings.

    Args:
        settings: Settings to use; defaults to the ones read from the environment.
        database_name: Optional database override (the test suite uses the test DB).
        embedder: Embedding backend; defaults to the one selected by EMBEDDING_BACKEND.
            Tests pass a lightweight fake instead of loading the model.
        static_dir: Folder with the built React app (``npm run build``). When given, the
            backend also serves the frontend from the same address (desktop app).

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
        embedder = create_embedder(settings)
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

    for router in (auth.router, catalog.router, diagnosis.router, knowledge_base.router, setup.router, users.router):
        app.include_router(router)
    if static_dir is not None:
        # Registered after the API routers, so an API path always wins over the catch-all.
        _mount_frontend(app, static_dir)

    return app


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serves the built React app from the same origin as the API.

    React Router handles paths such as /chat in the browser: a reload of that page asks the
    server for /chat, which must answer with index.html instead of 404.

    Args:
        app: Application to extend.
        static_dir: Folder produced by the Vite build (index.html, assets/).
    """
    root = static_dir.resolve()
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_frontend(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        # Real files next to index.html (e.g. favicon.svg); the containment check blocks "../" paths.
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(root / "index.html")


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
