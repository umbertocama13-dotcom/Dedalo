"""Shared fixtures, composed as building blocks:

settings -> test_engine -> db_connection -> client (+ auth headers)
settings -> test_engine -> app

``settings`` is parametrized on the two database backends, so every test that
touches the database runs once on MySQL and once on SQLite (test ids end with
[mysql] / [sqlite]). Pure unit tests do not request it and run once.

The app uses a fake embedder: the real model is loaded only by the tests marked "model".
"""

from collections.abc import Iterator
from pathlib import Path

import pymysql
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymysql.constants import CLIENT
from sqlalchemy import Connection, Engine

from app.config import Settings, get_settings
from app.db import create_db_engine, get_connection
from app.db_init import run_sqlite_scripts
from app.main import create_app
from app.services.security import create_access_token
from tests.fake_embedder import FakeEmbedder
from tests.memory_guard import MEMORY_WARNING, available_memory_mb, low_memory_message

DATABASE_DIR = Path(__file__).resolve().parents[2] / "database"
SEED_SCRIPTS = ("seed_catalog.sql", "seed.sql")

EXPERT_ID = 1
OPERATOR_ID = 2


def pytest_collection_finish(session: pytest.Session) -> None:
    """Warns before the real-model tests and stops if the available RAM is not enough.

    Runs after -m/-k filters are applied, so it acts only when model tests are really selected.
    """
    if not any(item.get_closest_marker("model") for item in session.items):
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(MEMORY_WARNING, yellow=True, bold=True)
    # --collect-only runs no test: nothing is loaded, so there is nothing to protect.
    if session.config.option.collectonly:
        return
    problem = low_memory_message(available_memory_mb())
    if problem:
        pytest.exit(problem, returncode=pytest.ExitCode.INTERRUPTED)


def _rebuild_mysql_test_database(settings: Settings) -> None:
    """Recreates the MySQL test database from schema.sql and the seed files.

    Args:
        settings: Settings with credentials and the test database name.

    Raises:
        RuntimeError: If the test database name equals the application one.
    """
    # schema.sql drops every table: never run it against the development database.
    if settings.db_test_name == settings.db_name:
        raise RuntimeError("DB_TEST_NAME must differ from DB_NAME: tests would wipe the application data")

    # PyMySQL runs one statement per execute() unless MULTI_STATEMENTS is enabled;
    # it is enabled only on this setup connection, never on the application engine.
    connection = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_test_name,
        charset="utf8mb4",
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        with connection.cursor() as cursor:
            for sql_file in ("schema.sql", *SEED_SCRIPTS):
                cursor.execute((DATABASE_DIR / sql_file).read_text(encoding="utf-8"))
                while cursor.nextset():
                    pass
        connection.commit()
    finally:
        connection.close()


@pytest.fixture(scope="session", params=["mysql", "sqlite"])
def settings(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Settings:
    # Tests never call a real AI backend, whatever the developer's .env says, and use the
    # calibrated conversation values, so a local tuning of .env cannot change their outcome.
    base = get_settings().model_copy(
        update={
            "ai_provider": "none",
            "semantic_use_fuzzy": True,
            "semantic_recall_threshold": 0.50,
            "semantic_match_threshold": 0.65,
            "disambiguation_score_gap": 0.05,
            "probability_temperature": 0.03,
            "probability_unknown_score": 0.60,
            "max_candidates": 5,
            "max_llm_questions": 3,
            "sample_diagnostics_csv": str(DATABASE_DIR / "sample_diagnostics.csv"),
        }
    )
    if request.param == "sqlite":
        # A fresh file in a pytest temporary folder: it can never be the desktop app's database.
        sqlite_path = tmp_path_factory.mktemp("sqlite") / "dedalo_test.db"
        return base.model_copy(update={"db_backend": "sqlite", "sqlite_path": str(sqlite_path)})
    return base.model_copy(update={"db_backend": "mysql"})


@pytest.fixture(scope="session")
def test_engine(settings: Settings) -> Iterator[Engine]:
    """Builds the test database once per backend and yields an engine on it."""
    if settings.db_backend == "sqlite":
        engine = create_db_engine(settings)
        run_sqlite_scripts(engine, [DATABASE_DIR / "sqlite" / "schema.sql", *(DATABASE_DIR / name for name in SEED_SCRIPTS)])
    else:
        _rebuild_mysql_test_database(settings)
        engine = create_db_engine(settings, settings.db_test_name)
    yield engine
    engine.dispose()


@pytest.fixture
def db_connection(test_engine: Engine) -> Iterator[Connection]:
    """Yields a connection whose changes are rolled back after each test."""
    with test_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture(scope="session")
def app(settings: Settings, test_engine: Engine) -> FastAPI:
    """Application wired to the test database (requesting test_engine guarantees it was built)."""
    return create_app(settings, database_name=settings.db_test_name, embedder=FakeEmbedder())


@pytest.fixture
def client(app: FastAPI, db_connection: Connection) -> Iterator[TestClient]:
    """HTTP client whose requests run inside the test's rolled-back transaction.

    Only the transaction boundary changes: routes, services, SQL and constraints are the real ones.
    """
    app.dependency_overrides[get_connection] = lambda: db_connection
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _bearer(user_id: int, role: str, settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id, role=role, settings=settings)}"}


@pytest.fixture
def expert_headers(settings: Settings) -> dict[str, str]:
    return _bearer(EXPERT_ID, "expert", settings)


@pytest.fixture
def operator_headers(settings: Settings) -> dict[str, str]:
    return _bearer(OPERATOR_ID, "operator", settings)
