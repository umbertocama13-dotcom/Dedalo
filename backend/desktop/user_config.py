"""Configuration of the desktop app.

The user's dedalo.env holds what may change per installation (JWT secret, AI provider,
matching thresholds). What makes the app a desktop app (SQLite, ONNX, local address,
bundled paths) is passed in code and cannot be overridden by that file.
"""

import secrets
from pathlib import Path

from app.config import Settings
from desktop.paths import DesktopPaths

ENV_TEMPLATE = """\
# Dedalo desktop — configuration of this installation.
# Close Dedalo before editing this file. Lines starting with # are ignored.

# Signs the login tokens. Generated at first start: changing it logs everybody out.
JWT_SECRET_KEY={secret}

# AI assistant: none = fully offline (default).
AI_PROVIDER=none
# To use OpenAI (paid; the conversation leaves this PC), set AI_PROVIDER=api and fill in:
# AI_API_URL=https://api.openai.com/v1
# AI_API_KEY=sk-...
# AI_API_MODEL=gpt-4o-mini

LOG_LEVEL=INFO
"""


def ensure_env_file(env_file: Path) -> bool:
    """Creates the configuration file with a random JWT secret, if it does not exist yet.

    An existing file is never modified: it may contain the user's changes, and a new
    secret would log everybody out.

    Args:
        env_file: Path of dedalo.env.

    Returns:
        True if the file was created now.
    """
    if env_file.exists():
        return False
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(ENV_TEMPLATE.format(secret=secrets.token_hex(32)), encoding="utf-8")
    return True


def load_settings(paths: DesktopPaths, port: int = 0) -> Settings:
    """Builds the settings of the desktop app.

    Args:
        paths: Paths of the installation.
        port: Local port the server will listen on.

    Returns:
        Settings read from dedalo.env, with the desktop-specific values forced.
    """
    # Init arguments take precedence over the env file in pydantic-settings, so a user
    # who writes DB_BACKEND=mysql in dedalo.env cannot break the installation.
    return Settings(
        _env_file=paths.env_file,
        db_backend="sqlite",
        sqlite_path=str(paths.database_file),
        embedding_backend="onnx",
        onnx_model_dir=str(paths.model_dir),
        sample_diagnostics_csv=str(paths.sample_csv),
        app_host="127.0.0.1",
        app_port=port,
        app_reload=False,
        # Frontend and API share the same address: no cross-origin requests to allow.
        cors_origins="",
    )
