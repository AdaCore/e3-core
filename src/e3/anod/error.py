from __future__ import annotations

from typing import TYPE_CHECKING

import e3.error

if TYPE_CHECKING:
    from typing import Optional
    from e3.os.process import Run

    assert Run  # Make pyflakes happy?


class AnodError(e3.error.E3Error):
    """Base Anod error."""

    pass


class SpecError(AnodError):
    """Invalid specification file."""

    pass


class SandBoxError(AnodError):
    """Invalid sandbox or wrong sandbox configuration."""

    pass


class ShellError(AnodError):
    """Error returned by a process spawned by Anod."""

    def __init__(
        self,
        message: str,
        origin: Optional[str] = None,
        process: Optional["Run"] = None,
    ):
        super().__init__(message, origin)
        self.process = process
