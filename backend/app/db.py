from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Connection, Engine, create_engine

from app.config import Settings


def create_db_engine(settings: Settings, database_name: str | None = None) -> Engine:
    """Creates the SQLAlchemy engine (connection pool) for MySQL.

    No connection is opened here: the pool connects lazily on first use.

    Args:
        settings: Application settings with the database credentials.
        database_name: Optional database override, used by the test suite.

    Returns:
        A configured SQLAlchemy engine.
    """
    return create_engine(
        settings.database_url(database_name),
        # MySQL silently closes idle connections after wait_timeout (8h by default):
        # pre_ping detects dead ones and recycle replaces them before that happens.
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def get_connection(request: Request) -> Iterator[Connection]:
    """FastAPI dependency yielding a connection inside a transaction.

    The transaction commits when the request handler succeeds and rolls back
    if it raises, so a failed write never leaves partial data.

    Args:
        request: Current request, used to reach the engine stored on app.state.

    Yields:
        An open connection bound to a transaction.
    """
    engine: Engine = request.app.state.engine
    with engine.begin() as connection:
        yield connection
