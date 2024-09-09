"""Submodule to mock Env."""

from __future__ import annotations

from typing import TYPE_CHECKING
from contextlib import contextmanager

from e3.env import Env


if TYPE_CHECKING:
    from typing import TypedDict, Iterator
    from typing_extensions import NotRequired

    class MockEnvConfig(TypedDict):
        """Config for MockEnv."""

        name: str
        """Mocked platform name"""
        version: NotRequired[str]
        """Mocked system version"""
        machine: NotRequired[str]
        """Mocked name of the target machine"""
        mode: NotRequired[str]
        """Mocked name of the mode"""


@contextmanager
def mock_env(config: MockEnvConfig | None = None) -> Iterator[Env]:
    """Mock e3.env.Env as a context or decorator.

    :param config: config for the mock
    :return: yield an Env iterator
    """
    _mock_env = Env()
    _mock_env.store()
    try:
        if config:
            _mock_env.set_build(**config)
        yield _mock_env
    finally:
        _mock_env.restore()
