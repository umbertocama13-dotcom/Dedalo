from collections.abc import Iterator
from typing import Any

from fastapi import Request
from sqlalchemy import Connection, Engine, create_engine, event

from app.config import Settings


def create_db_engine(settings: Settings, database_name: str | None = None) -> Engine:
    """Creates the SQLAlchemy engine (connection pool) for MySQL or SQLite.

    No connection is opened here: the pool connects lazily on first use.

    Args:
        settings: Application settings with the database backend and credentials.
        database_name: Optional MySQL database override, used by the test suite.

    Returns:
        A configured SQLAlchemy engine.
    """
    if settings.db_backend == "sqlite":
        engine = create_engine(
            settings.database_url(),
            # FastAPI runs sync routes in a thread pool, so a pooled connection may be
            # used by a thread other than the one that opened it.
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _configure_sqlite_connection)
        return engine

    return create_engine(
        settings.database_url(database_name),
        # MySQL silently closes idle connections after wait_timeout (8h by default):
        # pre_ping detects dead ones and recycle replaces them before that happens.
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def _configure_sqlite_connection(dbapi_connection: Any, connection_record: Any) -> None:
    """Configures every new SQLite connection.

    SQLite ignores FOREIGN KEY constraints unless this pragma is enabled on each
    connection.

    The journal mode is DELETE (SQLite's default), set explicitly. WAL mode was tried and
    discarded: it keeps recent commits in a separate dedalo.db-wal file, so copying only
    dedalo.db as a backup silently lost them. With a single user on the PC, WAL's better
    read/write concurrency brings nothing, while a self-contained file is safe to copy.

    Args:
        dbapi_connection: The sqlite3 connection just opened.
        connection_record: Pool bookkeeping object (unused).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=DELETE")
    cursor.close()


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
