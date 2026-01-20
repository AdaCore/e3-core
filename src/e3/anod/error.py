from __future__ import annotations

from typing import TYPE_CHECKING

import e3.error

if TYPE_CHECKING:
    from e3.os.process import Run


class AnodError(e3.error.E3Error):
    """Base Anod error."""


class SpecError(AnodError):
    """Invalid specification file."""


class SandBoxError(AnodError):
    """Invalid sandbox or wrong sandbox configuration."""


class ShellError(AnodError):
    """Error returned by a process spawned by Anod."""

    def __init__(
        self,
        message: str,
        origin: str | None = None,
        process: "Run" | None = None,
    ) -> None:
        super().__init__(message, origin)
        self.process = process
