from __future__ import annotations

from typing import TYPE_CHECKING

import json
import os

from e3.event import EventHandler
from e3.fs import cp, mkdir

if TYPE_CHECKING:
    from typing import Dict
    from e3.event import Event


class FileHandler(EventHandler):
    def __init__(self, log_dir: str) -> None:
        self.log_dir = log_dir

    def send_event(self, event: Event) -> bool:
        d = event.as_dict()
        prefix = "{}-{}".format(d["name"], d["uid"])
        log_file = os.path.join(self.log_dir, prefix + ".log")
        attach_dir = os.path.join(self.log_dir, prefix)
        mkdir(attach_dir)
        with open(log_file, "w") as fd:
            json.dump(d, fd, indent=2, sort_keys=True)
        for name, attachment in list(event.get_attachments().items()):
            cp(attachment[0], os.path.join(attach_dir, name))
        return True

    @classmethod
    def decode_config(cls, config_str: str) -> Dict[str, str]:
        return {"log_dir": config_str}

    def encode_config(self) -> str:
        return self.log_dir
