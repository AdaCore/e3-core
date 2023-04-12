from __future__ import annotations

from e3.error import E3Error

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3.os.process import Run


class VCSError(E3Error):
    def __init__(self, message: str, origin: str, process: Run | None = None):
        super().__init__(message, origin)
        self.origin = origin
        self.message = message
        self.process = process
