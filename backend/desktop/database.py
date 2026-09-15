import os

from app.config import Settings
from app.db import create_db_engine
from app.db_init import run_sqlite_scripts
from desktop.paths import DesktopPaths


def prepare_database(paths: DesktopPaths, settings: Settings) -> bool:
    """Creates the SQLite database with schema and catalog on first start.

    The database is built in a temporary file and renamed only when complete: if the
    first start is interrupted, the next one starts over instead of opening half a database.
    An existing database is never touched.

    Args:
        paths: Paths of the installation.
        settings: Desktop settings (only the database location is changed here).

    Returns:
        True if the database was created now.
    """
    if paths.database_file.exists():
        return False
    paths.database_file.parent.mkdir(parents=True, exist_ok=True)

    temporary = paths.database_file.with_suffix(".creating")
    temporary.unlink(missing_ok=True)
    engine = create_db_engine(settings.model_copy(update={"sqlite_path": str(temporary)}))
    try:
        run_sqlite_scripts(engine, [paths.sqlite_schema, paths.catalog_seed])
    finally:
        # Closes every pooled connection, so no handle keeps the file open during the rename.
        engine.dispose()
    os.replace(temporary, paths.database_file)
    return True
