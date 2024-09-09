"""Tests for e3.env."""

from __future__ import annotations

from typing import TYPE_CHECKING
import pytest

import logging
from e3.log import getLogger
from e3.env import Env
from e3.mock.env import mock_env

if TYPE_CHECKING:
    from typing import Callable
    from pytest import LogCaptureFixture

logger = getLogger("test MockEnv")


LOG_RUNNING_IN_WIN_2022 = "Running in Windows Server 2022"
LOG_ERROR_WIN_VERSION = (
    "Not running in correct windows version, expected version"
    " is 2022 but running in %(version)s"
)

ASSERT_PLATFORM_ERROR = (
    "Invalid platform : '%(platform)s' , function runs only in windows"
)


LINUX_ECHO_HELLO = "echo 'hello'"
WINDOWS_ECHO_HELLO = "Write-Output 'hello'"


def run_on_windows_2022() -> None:
    """Run a command in windows server 2022."""
    env = Env()
    version = env.build.os.version

    assert "windows" in env.platform, ASSERT_PLATFORM_ERROR % {
        "platform": env.platform,
    }
    if version == "2022":
        logging.info(LOG_RUNNING_IN_WIN_2022)
    else:
        logging.error(
            LOG_ERROR_WIN_VERSION % {"exp_version": " 2022", "version": version}
        )


def echo_hello() -> None:
    env = Env()

    if "windows" in env.platform:
        logger.info(WINDOWS_ECHO_HELLO)
    else:
        logger.info(LINUX_ECHO_HELLO)


@mock_env(config={"name": "x86_64-windows64", "version": "2022"})
def test_mock_env_decorator(caplog: LogCaptureFixture) -> None:
    """Test mock env decorator."""
    run_on_windows_2022()

    assert caplog.text.count(LOG_RUNNING_IN_WIN_2022) == 1


@mock_env()
def test_mock_env_decorator_without_config(caplog: LogCaptureFixture) -> None:
    """Test mock env decorator."""
    env = Env()
    version = env.build.os.version

    if "windows" not in env.platform:
        with pytest.raises(AssertionError) as ex:
            run_on_windows_2022()

        print(ex.value.args)
        assert ASSERT_PLATFORM_ERROR % {"platform": env.platform} in str(ex.value)
    else:
        run_on_windows_2022()
        if "2022" in version:
            assert caplog.text.count(LOG_RUNNING_IN_WIN_2022) == 1
        else:
            assert caplog.text.count(LOG_ERROR_WIN_VERSION % {"version": version}) == 1


@pytest.mark.parametrize(
    "platform_name,version,func,command_result",
    [
        ("x86_64-windows64", "2019", echo_hello, WINDOWS_ECHO_HELLO),
        ("aarch64-linux", "ubuntu24", echo_hello, LINUX_ECHO_HELLO),
    ],
)
def test_mock_env_with_context_config(
    platform_name: str,
    version: str,
    func: Callable,
    command_result: str,
    caplog: LogCaptureFixture,
) -> None:
    """Test mock_env as context."""
    with mock_env(config={"name": platform_name, "version": version}):
        func()
        assert caplog.text.count(command_result) == 1
