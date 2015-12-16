import time
import e3.decorator


def test_memoize():

    @e3.decorator.memoize
    def t(arg):
        return time.time()

    assert t(1) == t(1)
    assert t(1) != t(2)


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
