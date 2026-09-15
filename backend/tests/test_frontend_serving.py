"""The backend serves the built frontend from the same address (desktop app)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.config import Settings
from app.main import create_app
from tests.fake_embedder import FakeEmbedder

INDEX_HTML = "<!doctype html><div id='root'></div>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A minimal Vite build output, plus a file outside it that must never be served."""
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (folder / "assets" / "app.js").write_text("console.log('dedalo');", encoding="utf-8")
    (folder / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("top-secret", encoding="utf-8")
    return folder


@pytest.fixture
def frontend_client(settings: Settings, test_engine: Engine, dist: Path) -> TestClient:
    app = create_app(settings, database_name=settings.db_test_name, embedder=FakeEmbedder(), static_dir=dist)
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/chat", "/knowledge-base", "/setup"])
def test_frontend_routes_answer_with_index_html(frontend_client: TestClient, path: str) -> None:
    response = frontend_client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == INDEX_HTML


def test_built_files_are_served(frontend_client: TestClient) -> None:
    assert frontend_client.get("/assets/app.js").text == "console.log('dedalo');"
    assert frontend_client.get("/favicon.svg").text == "<svg></svg>"


def test_files_outside_the_build_folder_are_never_served(frontend_client: TestClient) -> None:
    response = frontend_client.get("/..%2Fsecret.txt")

    assert "top-secret" not in response.text


def test_api_routes_still_win(frontend_client: TestClient) -> None:
    assert frontend_client.get("/setup/status").json() == {"needs_setup": False}
    assert frontend_client.get("/diagnostics").status_code == 401


def test_without_static_dir_no_frontend_is_served(app_without_frontend: TestClient) -> None:
    assert app_without_frontend.get("/").status_code == 404


@pytest.fixture
def app_without_frontend(settings: Settings, test_engine: Engine) -> TestClient:
    return TestClient(create_app(settings, database_name=settings.db_test_name, embedder=FakeEmbedder()))
