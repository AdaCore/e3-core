"""File-based event handler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from e3.event import EventHandler, unique_id
from e3.fs import cp, mkdir

if TYPE_CHECKING:
    from e3.event import Event


class FileHandler(EventHandler):
    def __init__(self, log_dir: str) -> None:
        """Initialize file handler.

        :param log_dir: directory where to write event files
        """
        self.log_dir = log_dir

    def send_event(self, event: Event) -> bool:
        """Send event to file.

        :param event: event to send
        """
        d = event.as_dict()
        prefix = f"{event.name}-{event.uid}"
        event_file = Path(self.log_dir, f"{prefix}-{unique_id()}.json")
        attach_dir = Path(self.log_dir, prefix)
        mkdir(attach_dir)
        with event_file.open("w") as fd:
            json.dump(d, fd, indent=2, sort_keys=True)
        for name, attachment in list(event.get_attachments().items()):
            cp(attachment[0], attach_dir / name)
        return True

    @classmethod
    def decode_config(cls, config_str: str) -> dict[str, str]:
        """Decode configuration string.

        :param config_str: configuration string
        """
        return {"log_dir": config_str}

    def encode_config(self) -> str:
        return self.log_dir
