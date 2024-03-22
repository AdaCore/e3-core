"""Submodule that mocks Run."""

from __future__ import annotations

from typing import TYPE_CHECKING, overload
from functools import wraps
from unittest.mock import patch
from threading import Lock
import copy

import e3.os.process
from e3.os.process import Run, to_cmd_lines

if TYPE_CHECKING:
    from typing import Callable, Any, TypedDict
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


@overload
def mock_run(func: Callable[P, T]) -> Callable[P, T]: ...


@overload
def mock_run(func: None = None, config: MockRunConfig | None = None) -> RunPatcher: ...


def mock_run(
    func: Callable[P, T] | None = None, config: MockRunConfig | None = None
) -> RunPatcher | Callable[P, T]:
    """Mock e3.os.process.Run as a context or decorator.

    :param func: decorated function
    :param config: config for the mock
    :return: new RunPatcher instance or decorator
    """
    if func is not None:
        return RunPatcher().__call__(func=func)
    else:
        return RunPatcher(config)


class CommandResult:
    """Result of a command.

    When a command is supposed to be run, the actual status code and
    logs are taken from this object.
    """

    def __init__(
        self,
        cmd: list[str],
        status: int | None = None,
        raw_out: bytes | None = None,
        raw_err: bytes | None = None,
    ) -> None:
        """Initialize CommandResult.

        :param cmd: expected arguments of the command
        :param status: status code
        :param raw_out: raw output log
        :param raw_err: raw error log
        """
        self.cmd = cmd
        self.status = status if status is not None else 0
        self.raw_out = raw_out if raw_out is not None else b""
        self.raw_err = raw_err if raw_err is not None else b""

    def check(self, cmd: list[str]) -> None:
        """Check that cmd matches the expected arguments.

        :param cmd: actual command
        """
        if len(cmd) != len(self.cmd):
            raise UnexpectedCommandError(
                f"wrong number of arguments {cmd}, expected {self.cmd}"
            )

        for i, arg in enumerate(cmd):
            if arg != self.cmd[i] and self.cmd[i] != "*":
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
        pass


class MockRun(Run):
    """Mock e3.os.process.Run."""

    def __init__(self, config: MockRunConfig | None = None) -> None:
        """Initialize MockRun.

        :param config: MockRun configuration
        """
        self.config: MockRunConfig = copy.deepcopy(config) if config is not None else {}

    def add_result(self, result: CommandResult) -> None:
        """Queue a command result.

        :param result: new command result
        """
        self.config.setdefault("results", []).append(result)

    def __call__(self, cmds: AnyCmdLine, *args: Any, **kwargs: Any) -> Run:
        """Emulate how e3.os.process.Run.__init__ works.

        Once e3.os.process.Run is patched, this function will be called instead.

        :param cmds: command line
        :param args: unhandled arguments
        :param kwargs: unhandled keyword arguments
        """
        self.status: int | None = None
        self.raw_out: bytes | None = b""
        self.raw_err: bytes | None = b""

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

        return self


class RunPatcher:
    """Patch e3.os.process.Run when used as a context or decorator."""

    _mock_run: MockRun | None = None
    """Instance of MockRun."""
    _nested_count = 0
    """How many RunPatcher are currently alive."""
    _mock_init_lock = Lock()
    """Lock to avoid concurrency when patching/unpatching."""

    def __init__(self, config: MockRunConfig | None = None) -> None:
        """Initialize RunPatcher.

        :param config: MockRun configuration
        """
        self.config = config

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        """Decorate func when mock_run is used as a decorator.

        :param func: decorated function
        :return: a decorator for calling func
        """
        return self._decorate_callable(func)

    def __enter__(self) -> MockRun:
        """Enter the context manager.

        :return: MockRun instance
        """
        self.start()
        assert self.__class__._mock_run is not None
        return self.__class__._mock_run

    def __exit__(self, *args: Any) -> None:
        """Exit the context manager."""
        self.stop()

    def start(self) -> None:
        """Start mocking e3.os.process.Run."""
        with RunPatcher._mock_init_lock:
            self.__class__._nested_count += 1
            if self.__class__._nested_count == 1:
                # Only apply the patch once
                if isinstance(e3.os.process.Run, MockRun):
                    raise MockRunError("e3.os.process.Run already patched")

                self.__class__._mock_run = MockRun(config=self.config)
                self._run_patch = patch("e3.os.process.Run", self.__class__._mock_run)
                self._run_patch.start()

    def stop(self) -> None:
        """Stop mocking e3.os.process.Run."""
        with RunPatcher._mock_init_lock:
            self.__class__._nested_count -= 1
            if self.__class__._nested_count < 0:
                raise MockRunError("Called stop() before start().")

            if self.__class__._nested_count == 0:
                self.__class__._mock_run = None
                self._run_patch.stop()

    def _decorate_callable(self, func: Callable) -> Callable:
        """Decorate the callable function.

        :param func: decorated function
        :return: a decorator for calling func
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Callable:
            self.start()
            try:
                return func(*args, **kwargs)
            finally:
                self.stop()

        return wrapper
