"""Runs SQL script files on a SQLite database (desktop app and test suite).

MySQL databases are created with the mysql client (see README): only SQLite needs
this, because the desktop app must build its database by itself on first start.
"""

from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import Engine


def run_sqlite_scripts(engine: Engine, scripts: Sequence[Path]) -> None:
    """Executes whole SQL files, in order, and commits.

    Args:
        engine: Engine created with DB_BACKEND=sqlite.
        scripts: SQL files to execute.

    Raises:
        ValueError: If the engine is not a SQLite engine.
    """
    if engine.dialect.name != "sqlite":
        raise ValueError(f"run_sqlite_scripts needs a SQLite engine, got {engine.dialect.name}")

    raw_connection = engine.raw_connection()
    try:
        # sqlite3's executescript runs a file with many statements (execute() accepts one)
        # and parses string literals itself, so a ";" inside a text value is safe.
        for script in scripts:
            raw_connection.driver_connection.executescript(script.read_text(encoding="utf-8"))
        raw_connection.commit()
    finally:
        raw_connection.close()
