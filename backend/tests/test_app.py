"""Application wiring: startup checks, embedding warm-up, real transaction dependency, CORS, OpenAPI."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config import Settings
from app.main import create_app
from tests.fake_embedder import FakeEmbedder


def test_invalid_ai_configuration_stops_startup_before_loading_the_model(settings: Settings) -> None:
    broken = settings.model_copy(update={"ai_provider": "local", "ollama_model": ""})

    # No embedder is passed: if the model were loaded first, this test would take seconds.
    with pytest.raises(ValueError, match="OLLAMA_MODEL"):
        create_app(broken, database_name=settings.db_test_name)


def test_startup_warms_up_the_embedding_cache(settings: Settings, test_engine: Engine) -> None:
    app = create_app(settings, database_name=settings.db_test_name, embedder=FakeEmbedder())
    with test_engine.connect() as connection:
        distinct_symptoms = connection.execute(text("SELECT COUNT(DISTINCT symptom_description) FROM diagnostics")).scalar_one()

    # Entering the client context runs the lifespan startup.
    with TestClient(app):
        assert len(app.state.embedding_cache) == distinct_symptoms


def test_startup_survives_an_unreachable_database(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    # Port 1 for MySQL; for SQLite, a file inside a folder that does not exist cannot be opened.
    unreachable = settings.model_copy(update={"db_port": 1, "sqlite_path": "/nonexistent-dedalo-folder/dedalo.db"})
    app = create_app(unreachable, embedder=FakeEmbedder())
    # create_app() reconfigures logging with dictConfig, which removes pytest's capture
    # handler from the root logger: add it back for this test.
    root_logger = logging.getLogger()
    root_logger.addHandler(caplog.handler)
    try:
        with TestClient(app):
            assert len(app.state.embedding_cache) == 0
    finally:
        root_logger.removeHandler(caplog.handler)
    assert "warm-up skipped" in caplog.text


def test_real_connection_dependency_serves_requests(app: FastAPI, operator_headers: dict[str, str]) -> None:
    # No dependency override here: the request opens and commits its own transaction.
    # It only reads, so the test database is left untouched.
    response = TestClient(app).get("/families", headers=operator_headers)

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_cors_allows_only_configured_origins(app: FastAPI, settings: Settings) -> None:
    client = TestClient(app)
    allowed_origin = settings.cors_origin_list[0]
    preflight = {"Access-Control-Request-Method": "POST"}

    allowed = client.options("/diagnosis", headers={**preflight, "Origin": allowed_origin})
    denied = client.options("/diagnosis", headers={**preflight, "Origin": "http://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == allowed_origin
    assert "access-control-allow-origin" not in denied.headers


def test_openapi_documents_every_route(app: FastAPI) -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert set(paths) == {
        "/auth/login",
        "/auth/me",
        "/families",
        "/families/{family_id}/phases",
        "/diagnosis",
        "/diagnostics",
        "/diagnostics/export",
        "/diagnostics/import-template",
        "/diagnostics/import",
        "/diagnostics/{diagnostic_id}",
        "/setup/status",
        "/setup",
        "/users",
    }
