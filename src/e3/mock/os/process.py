"""Submodule that mocks Run."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from unittest.mock import patch
from contextlib import contextmanager
import copy
import fnmatch

from e3.os.process import Run, to_cmd_lines

if TYPE_CHECKING:
    from typing import Any, TypedDict
    from collections.abc import Iterator, Iterable
    from typing_extensions import NotRequired, ParamSpec, TypeVar
    from e3.os.process import AnyCmdLine

    P = ParamSpec("P")
    T = TypeVar("T")

    class MockRunConfig(TypedDict):
        """Config for MockRun."""

        results: NotRequired[list[CommandResult]]
        """Mocked results of expected commands"""


class MockRunError(Exception):
    """Error raised by mock_run."""

    pass


class UnexpectedCommandError(MockRunError):
    """Error raised when MockRun receives an unexpected command."""

    pass


@contextmanager
def mock_run(config: MockRunConfig | None = None) -> Iterator[MockRun]:
    """Mock e3.os.process.Run as a context or decorator.

    :param config: config for the mock
    :return: new MockRun instance
    """
    run = MockRun(config=config)
    with patch("e3.os.process.Run", run):
        yield run


class ArgumentChecker(Protocol):
    """Argument checker."""

    def check(self, arg: str) -> bool:
        """Check an argument.

        :param arg: the argument
        :return: if the argument is valid
        """
        ...

    def __repr__(self) -> str:
        """Return a textual representation of the expected argument."""
        ...


class GlobChecker(ArgumentChecker):
    """Check an argument against a glob."""

    def __init__(self, pattern: str) -> None:
        """Initialize GlobChecker.

        :param pattern: the glob pattern
        """
        self.pattern = pattern

    def check(self, arg: str) -> bool:
        """See ArgumentChecker."""
        return fnmatch.fnmatch(arg, self.pattern)

    def __repr__(self) -> str:
        """See ArgumentChecker."""
        return self.pattern.__repr__()


class SideEffect(Protocol):
    """Function to be called when a mocked command is called."""

    def __call__(
        self, result: CommandResult, cmd: list[str], *args: Any, **kwargs: Any
    ) -> None:
        """Run when the mocked command is called.

        :param result: the mocked command
        :param cmd: actual arguments of the command
        :param args: additional arguments for Run
        :param kwargs: additional keyword arguments for Run
        """
        ...


class CommandResult:
    """Result of a command.

    When a command is supposed to be run, the actual status code and
    logs are taken from this object.
    """

    def __init__(
        self,
        cmd: list[str | ArgumentChecker],
        status: int | None = None,
        raw_out: bytes = b"",
        raw_err: bytes = b"",
        side_effect: SideEffect | None = None,
    ) -> None:
        """Initialize CommandResult.

        :param cmd: expected arguments of the command
        :param status: status code
        :param raw_out: raw output log
        :param raw_err: raw error log
        :param side_effect: a function to be called when the command is called
        """
        self.cmd = cmd
        self.status = status if status is not None else 0
        self.raw_out = raw_out
        self.raw_err = raw_err
        self.side_effect = side_effect

    def check(self, cmd: list[str]) -> None:
        """Check that cmd matches the expected arguments.

        :param cmd: actual command
        """
        if len(cmd) != len(self.cmd):
            raise UnexpectedCommandError(
                f"wrong number of arguments {cmd}, expected {self.cmd}"
            )

        for i, arg in enumerate(cmd):
            checker = self.cmd[i]
            if isinstance(checker, str):
                if arg == checker or checker == "*":
                    continue
            elif checker.check(arg):
                continue

            raise UnexpectedCommandError(
                f"unexpected arguments {cmd}, expected {self.cmd}"
            )

    def __call__(self, cmd: list[str], *args: Any, **kwargs: Any) -> None:
        """Allow to run code to emulate the command.

        This function is called when a command is supposed to be run by Run. It
        takes the same arguments as Run.__init__.

        :param cmd: actual arguments of the command
        :param args: additional arguments for Run
        :param kwargs: additional keyword arguments for Run
        """
        if self.side_effect:
            self.side_effect(self, cmd, *args, **kwargs)


class MockRun(Run):
    """Mock e3.os.process.Run."""

    def __init__(self, config: MockRunConfig | None = None) -> None:
        """Initialize MockRun.

        :param config: MockRun configuration
        """
        self.config: MockRunConfig = copy.deepcopy(config) if config is not None else {}
        self.call_count = 0

    @property
    def all_called(self) -> bool:
        """Check all expected commands have been run."""
        return not self.config.get("results", [])

    def add_result(self, result: CommandResult | Iterable[CommandResult]) -> None:
        """Queue one or multiple command results.

        :param result: new command results
        """
        if isinstance(result, CommandResult):
            result = [result]

        self.config.setdefault("results", []).extend(result)

    def __call__(self, cmds: AnyCmdLine, *args: Any, **kwargs: Any) -> Run:
        """Emulate how e3.os.process.Run.__init__ works.

        Once e3.os.process.Run is patched, this function will be called instead.

        :param cmds: command line
        :param args: unhandled arguments
        :param kwargs: unhandled keyword arguments
        """
        self.status: int | None = None
        self.raw_out: bytes = b""
        self.raw_err: bytes = b""

        cmds = to_cmd_lines(cmds)
        results: list[CommandResult] | None = self.config.get("results")

        for cmd in cmds:
            # Get next queued result
            result = results.pop(0) if results else None
            # Make sure we are expecting a command
            if result is None:
                raise UnexpectedCommandError(f"unexpected command {cmd}")

            # Check received command
            result.check(cmd)

            # Call the result, forwarding arguments
            result(cmd, *args, **kwargs)

            # Update the output
            self.status = result.status
            self.raw_out += result.raw_out
            self.raw_err += result.raw_err
            self.call_count += 1

        return self
