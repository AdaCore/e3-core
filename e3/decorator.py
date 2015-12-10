"""Decorators.

to enable/disable a function, to memoize a function results...
"""
from __future__ import absolute_import

from functools import partial


def enabled(func):
    """no-op. Do not change function behaviour.

    >>> @enabled
    ... def foo():
    ...     print "I'm foo"
    >>> foo()
    I'm foo

    :param func: function to decorate
    """
    return func


def disabled(func):
    """Disable the provided function, and does nothing.

    >>> @disabled
    ... def foo():
    ...     print "I'm foo"
    >>> foo()

    :param func: function to decorate
    """
    del func

    def empty_func(*args, **kargs):
        del args, kargs
        pass
    return empty_func


class memoize(object):
    """Memoize function return values.

    Avoid repeating the calculation of results for previously-processed
    inputs.

    >>> import random
    >>> @memoize
    ... def long_computation(r):
    ...     del r
    ...     return random.random()
    >>> k = long_computation(42)
    >>> l = long_computation(42)
    >>> k == l
    True
    >>> j = long_computation(666)
    >>> k == j
    False
    """

    def __init__(self, func):
        """Initialize the decorator.

        :param func: function to decorate
        """
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        """Return the cache value if exist, else call func."""
        if kwargs:
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

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        del objtype
        return partial(self.__call__, obj)
