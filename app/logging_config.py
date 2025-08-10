from __future__ import annotations

import logging
from logging import Logger

from .config import settings


def setup_logging() -> Logger:
    """Configure root logger for the application."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("arena_bot")



