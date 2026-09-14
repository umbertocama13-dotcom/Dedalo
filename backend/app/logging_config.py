import logging.config


def configure_logging(level: str = "INFO") -> None:
    """Configures application-wide logging in a single place.

    Called once from create_app(); modules only call logging.getLogger(__name__).

    Args:
        level: Root log level name (e.g. "DEBUG", "INFO").
    """
    logging.config.dictConfig(
        {
            "version": 1,
            # Keep uvicorn's own loggers alive instead of silencing them.
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s"},
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "standard"},
            },
            "root": {"handlers": ["console"], "level": level.upper()},
        }
    )
