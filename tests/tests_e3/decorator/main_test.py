"""Tests for e3.decorator."""

import secrets

import pytest

import e3.decorator

# Test return value for memoize decorator
TEST_MEMOIZE_RETURN_VALUE = 22


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_memoize() -> None:
    """Test memoize."""
    # First generate a function returning random values so that we
    # can see whether the cache is used or not

    @e3.decorator.memoize
    def t(arg: int | list[int]) -> float:
        """Do foo."""
        del arg
        return secrets.randbelow(1_000_000_000)

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
        def t(self, arg: int) -> float:
            del arg
            return secrets.randbelow(1_000_000_000)

    # same instance use the same cache
    c_instance = C()
    assert c_instance.t(2) == c_instance.t(2)

    # but not different instances
    assert C().t(2) != C().t(2)


def test_enabled() -> None:
    """Test enabled."""

    @e3.decorator.enabled
    def foo() -> int:
        return TEST_MEMOIZE_RETURN_VALUE

    assert foo() == TEST_MEMOIZE_RETURN_VALUE


def test_disabled() -> None:
    """Test disabled."""

    @e3.decorator.disabled
    def foo() -> int:
        return TEST_MEMOIZE_RETURN_VALUE

    assert foo() is None
