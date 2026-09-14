"""Single entry point to start the API: python run.py (from the backend/ folder).

Host, port and reload come from .env, so Dockerfile, CI and terminal never repeat them.
"""

import uvicorn

from app.config import get_settings


def main() -> None:
    """Starts uvicorn with the settings read from the environment."""
    settings = get_settings()
    uvicorn.run(
        # factory=True: uvicorn calls create_app() itself, so no app object is built at import time.
        "app.main:create_app",
        factory=True,
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
    )


if __name__ == "__main__":
    main()
