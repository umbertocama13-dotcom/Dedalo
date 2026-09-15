"""Where the desktop app finds its read-only resources and keeps the user's data.

Resources (frontend build, SQL scripts, sample CSV, ONNX model) use the same relative
layout in the repository and in the PyInstaller bundle, so one set of paths serves both.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

MODEL_FOLDER = "sentence-bert-base-italian-xxl-uncased"


@dataclass(frozen=True)
class DesktopPaths:
    """Resource and data locations of one desktop installation."""

    resources: Path
    data: Path

    @property
    def database_file(self) -> Path:
        return self.data / "dedalo.db"

    @property
    def env_file(self) -> Path:
        return self.data / "dedalo.env"

    @property
    def log_file(self) -> Path:
        return self.data / "logs" / "dedalo.log"

    @property
    def lock_file(self) -> Path:
        return self.data / "dedalo.lock"

    @property
    def sqlite_schema(self) -> Path:
        return self.resources / "database" / "sqlite" / "schema.sql"

    @property
    def catalog_seed(self) -> Path:
        return self.resources / "database" / "seed_catalog.sql"

    @property
    def sample_csv(self) -> Path:
        return self.resources / "database" / "sample_diagnostics.csv"

    @property
    def frontend_dist(self) -> Path:
        return self.resources / "frontend" / "dist"

    @property
    def model_dir(self) -> Path:
        return self.resources / "backend" / "models" / MODEL_FOLDER


def resource_dir() -> Path:
    """Returns the folder holding the bundled resources.

    Returns:
        PyInstaller's extraction folder when packaged, otherwise the repository root.
    """
    # PyInstaller sets sys._MEIPASS to the folder where the bundled files live.
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is not None:
        return Path(bundle)
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """Returns the per-user folder for database, configuration and logs.

    DEDALO_DATA_DIR overrides it, e.g. to try the app without touching a real installation.

    Returns:
        %LOCALAPPDATA%\\Dedalo on Windows, $XDG_DATA_HOME/dedalo (or ~/.local/share/dedalo) elsewhere.
    """
    override = os.environ.get("DEDALO_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Dedalo"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "dedalo"


def get_paths() -> DesktopPaths:
    """Returns the paths of the current installation."""
    return DesktopPaths(resources=resource_dir(), data=user_data_dir())
