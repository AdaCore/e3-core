from __future__ import annotations

from typing import TYPE_CHECKING

import json
import mimetypes
import tempfile
from contextlib import closing

from e3.event import EventHandler, unique_id
from e3.fs import rm
from e3.os.process import Run
from e3.sys import python_script

if TYPE_CHECKING:
    from typing import Dict, Optional
    from e3.event import Event


class S3Handler(EventHandler):
    """Event handler that relies on AWS S3."""

    def __init__(
        self,
        event_s3_url: str,
        log_s3_url: str,
        sse: str = "AES256",
        profile: Optional[str] = None,
    ) -> None:
        self.event_s3_url = event_s3_url
        self.log_s3_url = log_s3_url
        self.aws_profile = profile
        self.sse = sse

    @classmethod
    def decode_config(cls, config_str: str) -> Dict[str, Optional[str]]:
        event_s3_url, log_s3_url, sse, aws_profile = config_str.split(",", 3)
        return {
            "event_s3_url": event_s3_url,
            "log_s3_url": log_s3_url,
            "sse": sse,
            "profile": aws_profile if aws_profile else None,
        }

    def encode_config(self) -> str:
        return "{},{},{},{}".format(
            self.event_s3_url,
            self.log_s3_url,
            self.sse,
            self.aws_profile if self.aws_profile is not None else "",
        )

    def s3_prefix(self, event: Event) -> str:
        """Additional prefix that depends on the event itself.

        This hook allows a user to add a prefix that depends on the event itself.
        Note that sufixes are still automatically computed so distinct events can
        return the same prefix. The final s3 url used will be
        {log_s3_url}/{s3_prefix}{automatic suffix} for logs and
        {event_s3_url}/{s3_prefix}{automatic suffix} for events metadata.

        :param event: an event
        :return: the prefix
        """
        return ""

    def send_event(self, event: Event) -> bool:
        def s3_cp(from_path: str, s3_url: str) -> bool:
            cmd = ["s3", "cp", f"--sse={self.sse}"]
            if self.aws_profile:
                cmd.append(f"--profile={self.aws_profile}")
            cmd += [from_path, s3_url]

            s3 = Run(python_script("aws") + cmd, output=None)
            return s3.status == 0

        # Push attachments to s3 and keep track of their url.
        s3_attachs = {}
        for name, attach in list(event.get_attachments().items()):
            attach_path = attach[0]
            # Push the attachment
            s3_url = f"{self.log_s3_url}/{self.s3_prefix(event)}{event.uid}/{name}"
            success = s3_cp(attach_path, s3_url)
            if not success:
                return False
            else:
                ctype, encoding = mimetypes.guess_type(attach_path)
                s3_attachs[name] = {
                    "s3_url": s3_url,
                    "encoding": encoding,
                    "ctype": ctype,
                }

        # Create the JSON to send on the event bucket
        s3_event = {"attachments": s3_attachs, "event": event.as_dict()}

        try:
            tempfile_name = None
            with closing(tempfile.NamedTemporaryFile(mode="w", delete=False)) as fd:
                tempfile_name = fd.name
                json.dump(s3_event, fd)

            # Note that an event can be sent several times with a different
            # status. As a consequence the target url in s3 should be different
            # for call to send.
            success = s3_cp(
                tempfile_name,
                f"{self.event_s3_url}/{self.s3_prefix(event)}"
                f"{event.uid}-{unique_id()}.s3",
            )

            if not success:
                return False
            else:
                return True
        finally:
            if tempfile_name is not None:
                rm(tempfile_name)
