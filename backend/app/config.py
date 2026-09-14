from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Resolve .env relative to this file, so settings load the same way whether the
# app is started from the project root, from backend/ or by pytest.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and backend/.env.

    Real environment variables take precedence over values in the .env file.
    """

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str = "dedalo"
    db_test_name: str = "dedalo_test"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    match_score_threshold: float = 80.0

    ai_provider: Literal["none", "api", "local"] = "none"
    ai_api_url: str = ""
    ai_api_key: str = ""
    ai_api_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""

    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_reload: bool = False

    def database_url(self, database_name: str | None = None) -> URL:
        """Builds the SQLAlchemy connection URL.

        Args:
            database_name: Database to connect to. Defaults to ``db_name``;
                the test suite passes ``db_test_name``.

        Returns:
            A URL object, which escapes special characters in the password.
        """
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=database_name or self.db_name,
            query={"charset": "utf8mb4"},
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """Returns the comma-separated CORS_ORIGINS value as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Returns the settings instance, read from the environment only once.

    Returns:
        The cached application settings.
    """
    return Settings()
