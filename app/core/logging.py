
"""Structured JSON logging configuration."""

import logging
import sys

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Adds service name and standard fields to every log record."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["service"] = "notification-service"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger to emit JSON to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(logger)s %(message)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)