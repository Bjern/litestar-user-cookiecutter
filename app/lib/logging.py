"""Structured logging configuration using loguru."""

import logging
import pathlib
import re
import sys
import warnings

from loguru import logger

from app.lib.settings import get_settings

# Patterns that should be redacted in log output
SENSITIVE_PATTERNS = re.compile(
    r"(password_hash|password|secret|token|authorization|cookie|session)"
    r"(['\"]?\s*[:=]\s*['\"]?)"
    r"(.+?)(?=[,;'\"}{]|$)",
    re.IGNORECASE,
)
REDACTED = "***REDACTED***"


def _redact(message: str) -> str:
    """Replace sensitive values in log messages."""
    return SENSITIVE_PATTERNS.sub(rf"\1\2{REDACTED}", message)


class InterceptHandler(logging.Handler):
    """Route stdlib logging records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, _redact(record.getMessage())
        )


LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"


def setup_logging() -> None:
    """Configure loguru as the sole logging backend."""
    settings = get_settings()

    # Remove default loguru handler
    logger.remove()

    # Console sink — human-readable, colored
    logger.add(
        sys.stderr,
        format=LOG_FORMAT,
        level=settings.log_level,
        colorize=True,
        filter=lambda record: _apply_redaction(record),  # type: ignore[arg-type]
    )

    # File sink — structured, rotated, for LLM analysis
    pathlib.Path("logs").mkdir(exist_ok=True)
    logger.add(
        "logs/app.log",
        format=LOG_FORMAT,
        level=settings.log_level,
        rotation="7 days",
        retention="30 days",
        compression="gz",
        serialize=True,  # JSON lines — ideal for LLM parsing
        filter=lambda record: _apply_redaction(record),  # type: ignore[arg-type]
    )

    # Suppress PyJWT key-length warning (litestar-users manages the key internally)
    warnings.filterwarnings(
        "ignore", message=".*HMAC key.*", category=DeprecationWarning
    )
    warnings.filterwarnings("ignore", message=".*HMAC key.*")

    # Intercept all stdlib loggers
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Quieten noisy libraries
    for name in ("aiosqlite", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _apply_redaction(record: dict) -> bool:  # type: ignore[arg-type]
    """Loguru filter that redacts sensitive data in-place. Always returns True."""
    record["message"] = _redact(record["message"])
    return True
