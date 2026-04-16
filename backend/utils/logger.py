"""
utils/logger.py — Structured logging via loguru.

FIX: LOG_FORMAT defaults to "text" for local dev (human-readable).
     Set LOG_FORMAT=json in .env for production JSON logs.
"""
from __future__ import annotations

import sys
from loguru import logger as _logger


def _setup_logger():
    """Configure loguru based on environment settings."""
    # Import here to avoid circular import at module load
    from config import get_settings
    settings = get_settings()

    # Remove default loguru sink
    _logger.remove()

    is_json = settings.LOG_FORMAT.lower() == "json"

    _logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        level=settings.LOG_LEVEL,
        colorize=not is_json,
        serialize=is_json,
    )
    return _logger


logger = _setup_logger()
