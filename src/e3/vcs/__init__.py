"""Version control system abstractions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from e3.error import E3Error

if TYPE_CHECKING:
    from e3.os.process import Run


class VCSError(E3Error):
    def __init__(self, message: str, origin: str, process: Run | None = None) -> None:
        """Initialize VCSError.

        :param message: error message
        :param origin: origin of the error
        :param process: process that caused the error
        """
        super().__init__(message, origin)
        self.origin = origin
        self.message = message
        self.process = process
