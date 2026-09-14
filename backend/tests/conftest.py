"""Shared fixtures, composed as building blocks:

settings -> test_engine -> db_connection -> client (+ auth headers)
settings -> test_engine -> app

Fixtures that touch MySQL are only created when a test requests them, so pure unit
tests (e.g. the fuzzy matcher) run without a database.
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
from app.main import create_app
from app.services.security import create_access_token

DATABASE_DIR = Path(__file__).resolve().parents[2] / "database"

EXPERT_ID = 1
OPERATOR_ID = 2


def _rebuild_test_database(settings: Settings) -> None:
    """Recreates the test database from schema.sql and seed.sql.

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
            for sql_file in ("schema.sql", "seed.sql"):
                cursor.execute((DATABASE_DIR / sql_file).read_text(encoding="utf-8"))
                while cursor.nextset():
                    pass
        connection.commit()
    finally:
        connection.close()


@pytest.fixture(scope="session")
def settings() -> Settings:
    # Tests never call a real AI backend, whatever the developer's .env says.
    return get_settings().model_copy(update={"ai_provider": "none"})


@pytest.fixture(scope="session")
def test_engine(settings: Settings) -> Iterator[Engine]:
    """Rebuilds the test database once per test session and yields an engine on it."""
    _rebuild_test_database(settings)
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
    """Application wired to the test database (requesting test_engine guarantees it was rebuilt)."""
    return create_app(settings, database_name=settings.db_test_name)


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
