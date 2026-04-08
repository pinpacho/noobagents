"""Structured JSON logging configuration."""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from src.config import get_settings


def setup_logging() -> None:
    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Quiet noisy third-party loggers
    for name in ("httpx", "httpcore", "opentelemetry", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
