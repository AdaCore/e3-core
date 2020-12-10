from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:

    from typing import NoReturn

    def assert_never(value: NoReturn) -> NoReturn:
        raise AssertionError(f"Unhandled value: {value} ({type(value).__name__})")
