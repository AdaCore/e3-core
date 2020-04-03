from random import random

import e3.decorator

import pytest


def test_memoize():
    # First generate a function returning random values so that we
    # can see whether the cache is used or not

    @e3.decorator.memoize
    def t(arg):
        """Do foo."""
        del arg
        return random()

    assert "Do foo." in t.__repr__()

    assert t(1) == t(1)
    assert t(1) != t(2)

    # kwargs not supported
    with pytest.raises(TypeError):
        assert t(arg=1)

    # cache not used when non-hashable arguments
    assert t([1, 2, 3]) != t([1, 2, 3])

    # Verify that the cache is working also when
    # calling instance methods

    class C:
        @e3.decorator.memoize
        def t(self, arg):
            del arg
            return random()

    # same instance use the same cache
    c_instance = C()
    assert c_instance.t(2) == c_instance.t(2)

    # but not different instances
    assert C().t(2) != C().t(2)


def test_enabled():
    @e3.decorator.enabled
    def foo():
        return 22

    assert foo() == 22


def test_disabled():
    @e3.decorator.disabled
    def foo():
        return 22

    assert foo() is None
