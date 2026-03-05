"""Tests for the logging module."""

import logging

from octoauthor.core.logging import get_logger


class TestGetLogger:
    def test_returns_logger(self) -> None:
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_logger_has_handlers(self) -> None:
        get_logger("test.handlers")
        root = logging.getLogger("octoauthor")
        assert len(root.handlers) > 0

    def test_multiple_calls_same_logger(self) -> None:
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        assert logger1 is logger2
