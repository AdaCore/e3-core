"""Decorators.

to enable/disable a function, to memoize a function results...
"""


from __future__ import annotations

from functools import partial

from typing import TYPE_CHECKING
from warnings import warn

if TYPE_CHECKING:
    from typing import Any, Callable, Dict


def enabled(func: Callable) -> Callable:
    """no-op. Do not change function behaviour.

    If you write the following code::

        @enabled
        def foo():
            print("I'm foo")

    Then calling ``foo()`` will return "I'm foo"

    :param func: function to decorate
    """
    return func


def disabled(func: Callable) -> Callable:
    """Disable the provided function, and does nothing.

    If you write the following code::

        @disabled
        def foo():
            print("I'm foo")

    Then calling ``foo()`` will return None

    :param func: function to decorate
    """
    del func

    def empty_func(*args: Any, **kargs: Any) -> None:
        del args, kargs

    return empty_func


class memoize:
    """Memoize function return values.

    Avoid repeating the calculation of results for previously-processed
    inputs.

    If you write the following code::

        import random
        @memoize
        def long_computation(r):
            del r
            return random.random()

    Then you will have::

       long_computation(42) == long_computation(42)

    Calling the same function twice with the same paramaters returns the same
    result.

    Calling the function with the special keyword argument reset_cache=True
    force a call to the decorated function, skipping the cache.

    No keyword argument can be passed to the decorated function.
    """

    def __init__(self, func: Callable):
        """Initialize the decorator.

        :param func: function to decorate
        """
        self.func = func
        self.cache: Dict[tuple, Any] = {}
        warn(
            "this decorator will be removed in a later version of e3-core, "
            "please use functools.lru_cache instead",
            category=DeprecationWarning,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Return the cache value if exist, else call func."""
        if kwargs:
            if len(kwargs) == 1 and kwargs.get("reset_cache"):
                # special handling of reset_cache, clean the cache
                if args in self.cache:
                    del self.cache[args]
            else:
                raise TypeError("memoize does not support keyword arguments")
        try:
            return self.cache[args]
        except KeyError:
            value = self.func(*args)
            self.cache[args] = value
            return value
        except TypeError:
            # non-hashable arguments, skip the cache
            return self.func(*args)

    def __repr__(self) -> str:
        """Return the function's docstring."""
        return self.func.__doc__ or ""

    def __get__(self, obj: Any, objtype: Any) -> Any:
        """Support instance methods."""
        del objtype
        return partial(self.__call__, obj)
