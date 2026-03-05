"""Logging-based event handler."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import e3.log
from e3.event import EventHandler

if TYPE_CHECKING:
    from e3.event import Event


class LoggingHandler(EventHandler):
    def __init__(self, logger_name: str = "", level: int = logging.DEBUG) -> None:
        """Initialize logging handler.

        :param logger_name: name of the logger to use
        :param level: logging level
        """
        self.logger_name = logger_name
        self.level = level
        self.log = e3.log.getLogger(logger_name)

    def send_event(self, event: Event) -> bool:
        """Send event to logger.

        :param event: event to send
        """
        d = event.as_dict()
        self.log.log(self.level, json.dumps(d, indent=2))
        return True

    @classmethod
    def decode_config(cls, config_str: str) -> dict[str, str | int]:
        """Decode configuration string.

        :param config_str: configuration string
        """
        logger_name, level = config_str.split(",")
        return {"logger_name": logger_name, "level": int(level)}

    def encode_config(self) -> str:
        return f"{self.logger_name},{self.level}"
