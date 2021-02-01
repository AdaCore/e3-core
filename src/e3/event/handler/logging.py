from __future__ import annotations

from typing import TYPE_CHECKING

import json
import logging

import e3.log
from e3.event import EventHandler

if TYPE_CHECKING:
    from typing import Dict
    from e3.event import Event


class LoggingHandler(EventHandler):
    def __init__(self, logger_name: str = "", level: int = logging.DEBUG) -> None:
        self.logger_name = logger_name
        self.level = level
        self.log = e3.log.getLogger(logger_name)

    def send_event(self, event: Event) -> bool:
        d = event.as_dict()
        self.log.log(self.level, json.dumps(d, indent=2))
        return True

    @classmethod
    def decode_config(cls, config_str: str) -> Dict[str, str | int]:
        logger_name, level = config_str.split(",")
        return {"logger_name": logger_name, "level": int(level)}

    def encode_config(self) -> str:
        return f"{self.logger_name},{self.level}"
