from __future__ import annotations

import gc
import time

from e3.weakref import WeakRef


class X:
    # Slots are used to make flake happy, otherwise, flake raise a B903 error.
    __slots__ = ("data", "__weakref__")

    def __init__(self, data: int) -> None:
        self.data = data


def test_weakref() -> None:
    strong = X(0)
    weak = WeakRef(strong)

    # Outside an opened context, `weak.value` must be None
    assert weak.value is None

    with weak as x:
        assert x.data == 0
        assert weak.value.data == 0

        # Also remove all strong references on x0
        del strong
        del x

        strong = None  # noqa
        x = None  # noqa

        assert x is None
        assert weak.value is not None
        assert weak.value.data == 0

    # Outside an opened context, `weak.value` must be None
    assert weak.value is None

    # Try to force the garbage collector.
    #
    # Note: It is not possible to really "force" the garbage collector, we can just
    # try.
    gc.collect()
    # Sleep and try again to collect everything, just in case.
    time.sleep(0.5)
    gc.collect()

    # Re-open the context, this time, `y` must be None as well as the current
    # strong reference since no strong reference exists.
    with weak as y:
        assert y is None
        assert weak.value is None


class WeakRefWithDefault(WeakRef[X, X]):
    def default(self) -> int:
        return X(10)


def test_weakref_with_default():
    weak = WeakRefWithDefault(None)
    with weak as x:
        pass
    with weak as y:
        pass
    assert x is y
