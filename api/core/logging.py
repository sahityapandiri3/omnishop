"""
Logging configuration for the API.

Usage:
    # In any file, use the contextual logger for automatic request/session ID inclusion:
    from middleware.logging_middleware import get_logger
    logger = get_logger(__name__)

    logger.info("Processing request")  # Will include [request_id][session_id] automatically

    # Or use standard logging (no auto request ID):
    import logging
    logger = logging.getLogger(__name__)
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

from core.config import settings


def setup_logging():
    """Configure logging for the application."""

    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure structlog processors
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Choose renderer based on format setting
    if settings.log_format == "json":
        # JSON format for production - easy to parse and search
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Console format for development - human readable with colors
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    structlog.configure(
        processors=shared_processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler - always present
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if settings.log_format == "json":
        # Simple format for JSON (structlog handles the formatting)
        console_format = "%(message)s"
    else:
        # Detailed format for development
        console_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    console_handler.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(console_handler)

    # File handler for production - useful for debugging
    if settings.environment == "production":
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_handler = RotatingFileHandler(
            log_dir / "api.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)  # Capture everything in file
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        root_logger.addHandler(file_handler)

        # Separate error log
        error_handler = RotatingFileHandler(
            log_dir / "api_errors.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s\n%(exc_info)s")
        )
        root_logger.addHandler(error_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("databases").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Log startup info
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={settings.log_level}, format={settings.log_format}, env={settings.environment}")


def get_log_level_for_env() -> str:
    """Get recommended log level based on environment."""
    env = getattr(settings, "environment", "development")
    if env == "production":
        return "INFO"
    elif env == "staging":
        return "DEBUG"
    else:
        return "DEBUG"
