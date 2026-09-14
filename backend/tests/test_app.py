"""Application wiring: startup checks, real transaction dependency, CORS, OpenAPI."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_invalid_ai_configuration_stops_startup(settings: Settings) -> None:
    broken = settings.model_copy(update={"ai_provider": "local", "ollama_model": ""})

    with pytest.raises(ValueError, match="OLLAMA_MODEL"):
        create_app(broken, database_name=settings.db_test_name)


def test_real_connection_dependency_serves_requests(app: FastAPI, operator_headers: dict[str, str]) -> None:
    # No dependency override here: the request opens and commits its own transaction.
    # It only reads, so the test database is left untouched.
    response = TestClient(app).get("/families", headers=operator_headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


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
        "/diagnostics/{diagnostic_id}",
        "/diagnostics/{diagnostic_id}/exceptions",
        "/diagnostics/{diagnostic_id}/exceptions/{exception_id}",
    }
