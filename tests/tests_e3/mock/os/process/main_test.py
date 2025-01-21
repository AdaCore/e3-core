"""Tests for e3.mock.os.process."""

from __future__ import annotations

from typing import TYPE_CHECKING
import subprocess
import time
import pytest

import e3.fs
import e3.os.fs
import e3.os.process
from e3.mock.os.process import mock_run, CommandResult, MockRun, UnexpectedCommandError

if TYPE_CHECKING:
    from typing import Any

    from e3.mock.os.process import MockRunConfig

# Mock the result of echo "hello"
ECHO_HELLO_RESULT = CommandResult(["echo", '"hello"'], raw_out=b"hello\n")

# Mock the result of echo "world"
ECHO_WORLD_RESULT = CommandResult(["echo", '"world"'], raw_out=b"world\n")

# Mock the result of echo "john"
ECHO_JOHN_RESULT = CommandResult(["echo", '"john"'], raw_out=b"john\n")

# Config for mock_run
MOCK_RUN_CONFIG: MockRunConfig = {"results": [ECHO_HELLO_RESULT, ECHO_WORLD_RESULT]}


class SleepCommandResult(CommandResult):
    """CommandResult that emulates the sleep command."""

    def __init__(self, seconds: float, /) -> None:
        """Initialize SleepCommandResult.

        :param seconds: seconds to sleep
        """
        self.seconds = seconds
        super().__init__(["sleep", str(seconds)])

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Sleep x seconds."""
        time.sleep(self.seconds)


def echo(msg: str) -> None:
    """Run echo "msg" with e3.os.process.Run.

    :param msg: message to echo
    """
    assert isinstance(e3.os.process.Run, MockRun), "e3.os.process.Run not patched"
    p = e3.os.process.Run(["echo", f'"{msg}"'], error=subprocess.PIPE)
    assert p.out.replace("\r", "") == f"{msg}\n"


def echo_hello() -> None:
    """Run echo "hello" with e3.os.process.Run."""
    echo("hello")


def echo_world() -> None:
    """Run echo "world" with e3.os.process.Run."""
    echo("world")

    assert e3.os.process.Run.all_called
    assert e3.os.process.Run.call_count == 2


@mock_run()
def test_mock_run_decorator() -> None:
    """Test mock_run as a decorator without config."""
    # Add results for both commands
    for result in [ECHO_HELLO_RESULT, ECHO_WORLD_RESULT]:
        e3.os.process.Run.add_result(result)

    echo_hello()
    echo_world()


@mock_run(config=MOCK_RUN_CONFIG)
def test_mock_run_decorator_config() -> None:
    """Test mock_run as a decorator with config."""
    echo_hello()
    echo_world()


def test_mock_run_context_config() -> None:
    """Test mock_run as a context with config."""
    with mock_run(config=MOCK_RUN_CONFIG) as run:
        assert e3.os.process.Run == run

        # Run both commands
        echo_hello()
        echo_world()


def test_mock_run_initial_add_result() -> None:
    """Test add_result before running any command."""
    with mock_run() as run:
        assert e3.os.process.Run == run

        # Add results for both commands
        for result in [ECHO_HELLO_RESULT, ECHO_WORLD_RESULT]:
            e3.os.process.Run.add_result(result)

        # Run both commands
        echo_hello()
        assert not e3.os.process.Run.all_called
        assert e3.os.process.Run.call_count == 1
        echo_world()


def test_mock_run_initial_add_results() -> None:
    """Test add_result with multiple results before running any command."""
    with mock_run() as run:
        assert e3.os.process.Run == run

        # Single call to add_result for multiple results
        e3.os.process.Run.add_result([ECHO_HELLO_RESULT, ECHO_WORLD_RESULT])

        # Run both commands
        echo_hello()
        assert not e3.os.process.Run.all_called
        assert e3.os.process.Run.call_count == 1
        echo_world()


def test_mock_run_sequential_add_result() -> None:
    """Test add_result before running each command."""
    with mock_run():
        # Add the result for first command
        e3.os.process.Run.add_result(ECHO_HELLO_RESULT)

        # Run first command
        echo_hello()
        assert e3.os.process.Run.all_called
        assert e3.os.process.Run.call_count == 1

        # Add the result for second command
        e3.os.process.Run.add_result(ECHO_WORLD_RESULT)

        # Run second command
        echo_world()


def test_mock_run_sleep() -> None:
    """Test where the sleep command is emulated."""
    with mock_run(config={"results": [SleepCommandResult(1)]}):
        e3.os.process.Run(["sleep", "1"])


def test_mock_run_unexpected_command() -> None:
    """Test where a command is run while not expected."""
    with mock_run(), pytest.raises(UnexpectedCommandError):
        e3.os.process.Run(["sleep", "1"])


@mock_run()
def test_mock_run_wrong_command() -> None:
    """Test where the wrong command is run."""
    e3.os.process.Run.add_result(ECHO_HELLO_RESULT)

    with pytest.raises(UnexpectedCommandError):
        e3.os.process.Run(["time"])


@mock_run()
def test_mock_run_unexpected_arguments() -> None:
    """Test where a command is run with unexpected arguments."""
    e3.os.process.Run.add_result(ECHO_HELLO_RESULT)

    with pytest.raises(UnexpectedCommandError):
        e3.os.process.Run(["echo", '"world"'])


def test_mock_run_multi_patch() -> None:
    """Test that mock_run called multiple times is handled properly."""
    with mock_run(), mock_run():
        e3.os.process.Run.add_result(ECHO_HELLO_RESULT)
        echo_hello()


def test_mock_run_nested() -> None:
    """Test that nested mock_run are handled properly."""
    with mock_run(config=MOCK_RUN_CONFIG) as run1:
        assert e3.os.process.Run == run1
        echo_hello()

        with mock_run(config={"results": [ECHO_JOHN_RESULT]}) as run2:
            assert e3.os.process.Run == run2
            echo("john")

            assert e3.os.process.Run.all_called
            assert e3.os.process.Run.call_count == 1

            with pytest.raises(UnexpectedCommandError):
                echo_world()

        assert e3.os.process.Run == run1
        echo_world()
