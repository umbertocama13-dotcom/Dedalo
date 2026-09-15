"""Desktop launcher pieces, without opening a window.

The last test starts the real server the way the packaged app does (SQLite file,
bundled frontend, first-start database) with a fake embedder instead of the ONNX model.
"""

import shutil
import socket
import sqlite3
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text

from desktop.database import prepare_database
from desktop.instance_lock import InstanceLock
from desktop.launcher import find_free_port, start_server, stop_server, wait_until_ready
from desktop.paths import DesktopPaths, get_paths, resource_dir
from desktop.user_config import ensure_env_file, load_settings
from tests.fake_embedder import FakeEmbedder


@pytest.fixture
def paths(tmp_path: Path) -> DesktopPaths:
    """Repository resources with a throwaway data folder."""
    return DesktopPaths(resources=resource_dir(), data=tmp_path / "data")


# --- Paths and configuration ------------------------------------------------------------


def test_development_resources_are_the_repository_files(paths: DesktopPaths) -> None:
    assert paths.sqlite_schema.is_file()
    assert paths.catalog_seed.is_file()
    assert paths.sample_csv.is_file()


def test_data_dir_can_be_overridden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEDALO_DATA_DIR", str(tmp_path))

    assert get_paths().data == tmp_path


def test_env_file_is_created_once_with_a_random_secret(tmp_path: Path) -> None:
    first, second = tmp_path / "a" / "dedalo.env", tmp_path / "b" / "dedalo.env"

    assert ensure_env_file(first) is True
    original = first.read_text(encoding="utf-8")
    first.write_text(original + "AI_PROVIDER=api\n", encoding="utf-8")

    assert ensure_env_file(first) is False
    assert first.read_text(encoding="utf-8").endswith("AI_PROVIDER=api\n")
    ensure_env_file(second)
    assert secret_line(first).startswith("JWT_SECRET_KEY=")
    assert secret_line(first) != secret_line(second)


def secret_line(env_file: Path) -> str:
    return next(line for line in env_file.read_text(encoding="utf-8").splitlines() if line.startswith("JWT_SECRET_KEY="))


def test_desktop_values_cannot_be_overridden_by_the_env_file(paths: DesktopPaths) -> None:
    ensure_env_file(paths.env_file)
    with paths.env_file.open("a", encoding="utf-8") as env:
        env.write("DB_BACKEND=mysql\nEMBEDDING_BACKEND=sentence-transformers\nAPP_HOST=0.0.0.0\nMAX_CANDIDATES=4\n")

    settings = load_settings(paths, port=8123)

    assert (settings.db_backend, settings.embedding_backend, settings.app_host) == ("sqlite", "onnx", "127.0.0.1")
    assert (settings.sqlite_path, settings.app_port, settings.cors_origin_list) == (str(paths.database_file), 8123, [])
    # Values that are not desktop-specific still come from the user's file.
    assert settings.max_candidates == 4
    assert len(settings.jwt_secret_key) == 64


def test_free_port_can_be_bound() -> None:
    port = find_free_port()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", port))


def test_only_one_instance_holds_the_lock(tmp_path: Path) -> None:
    first, second = InstanceLock(tmp_path / "dedalo.lock"), InstanceLock(tmp_path / "dedalo.lock")

    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


# --- Database ---------------------------------------------------------------------------


def test_first_start_creates_catalog_without_users_and_never_recreates(paths: DesktopPaths) -> None:
    ensure_env_file(paths.env_file)
    settings = load_settings(paths)

    assert prepare_database(paths, settings) is True
    engine = create_engine(f"sqlite:///{paths.database_file}")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM product_families")).scalar_one() == 3
        assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0
        connection.execute(text("DELETE FROM cycle_phases WHERE id = 12"))
    engine.dispose()

    assert prepare_database(paths, settings) is False
    engine = create_engine(f"sqlite:///{paths.database_file}")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM cycle_phases")).scalar_one() == 11
    engine.dispose()
    assert not paths.database_file.with_suffix(".creating").exists()


# --- The server as the packaged app starts it ------------------------------------------


def test_server_starts_serves_frontend_and_api_then_stops(tmp_path: Path) -> None:
    dist = tmp_path / "resources" / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    repository = resource_dir()
    resources = tmp_path / "resources"
    (resources / "database" / "sqlite").mkdir(parents=True)
    for relative in ("database/sqlite/schema.sql", "database/seed_catalog.sql", "database/sample_diagnostics.csv"):
        (resources / relative).write_bytes((repository / relative).read_bytes())
    paths = DesktopPaths(resources=resources, data=tmp_path / "data")
    ensure_env_file(paths.env_file)

    server, thread, url = start_server(paths, embedder=FakeEmbedder())
    try:
        assert wait_until_ready(server, thread, timeout=30)
        assert httpx.get(f"{url}setup/status").json() == {"needs_setup": True}
        assert httpx.get(f"{url}chat").text == "<div id='root'></div>"
        created = httpx.post(f"{url}setup", json={"username": "esperto", "password": "password-sicura"})
        assert (created.status_code, created.json()["sample_diagnostics_loaded"]) == (201, 36)
    finally:
        stop_server(server, thread)
    assert not thread.is_alive()
    assert paths.database_file.is_file()

    # The documented backup is "copy dedalo.db with Dedalo closed": the copy alone must hold every commit.
    backup = tmp_path / "backup.db"
    shutil.copyfile(paths.database_file, backup)
    connection = sqlite3.connect(backup)
    try:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM diagnostics").fetchone()[0] == 36
    finally:
        connection.close()
