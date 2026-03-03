"""Mypy type checking utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import NoReturn

    def assert_never(value: NoReturn) -> NoReturn:
        """Assert that a code path is unreachable for type checking.

        :param value: value that should never be reached
        """
        raise AssertionError(f"Unhandled value: {value} ({type(value).__name__})")
