"""Structured logging for OctoAuthor."""

import json
import logging
import sys
from typing import Any


class _JsonFormatter(logging.Formatter):
    """JSON log formatter for production use."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Include extra context fields
        for key in ("correlation_id", "agent_role", "url", "step", "tag", "server", "screenshot_file"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value
        return json.dumps(log_entry)


class _HumanFormatter(logging.Formatter):
    """Human-readable log formatter for development."""

    FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt="%H:%M:%S")


_configured = False


def _configure_root(level: str = "INFO", *, json_output: bool = False) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("octoauthor")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter() if json_output else _HumanFormatter())
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for name in ("httpx", "httpcore", "playwright", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name.

    Automatically configures the root octoauthor logger on first call.
    Log level is read from OCTOAUTHOR_LOG_LEVEL env var (default: INFO).
    """
    import os

    level = os.environ.get("OCTOAUTHOR_LOG_LEVEL", "INFO")
    json_output = os.environ.get("OCTOAUTHOR_LOG_FORMAT", "").lower() == "json"
    _configure_root(level, json_output=json_output)

    return logging.getLogger(name)
