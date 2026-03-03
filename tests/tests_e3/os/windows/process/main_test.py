"""Tests for e3.os.windows.process."""

import sys

import pytest

import e3.os.process

if sys.platform == "win32":
    from e3.os.windows.process import process_exit_code, wait_for_objects


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_invalid_handle() -> None:
    """Test invalid handle."""
    with pytest.raises(WindowsError):
        process_exit_code(42)


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_wait_for_objects() -> None:
    """Test wait for objects."""
    long_cmd = [sys.executable, "-c", "import time; time.sleep(40.0)"]
    short_cmd = [sys.executable, "-c", "pass"]

    p = e3.os.process.Run(long_cmd, bg=True)

    assert wait_for_objects([int(p.internal._handle)], timeout=1) is None, (
        "timeout was expected"
    )
    p.kill()

    p0 = e3.os.process.Run(long_cmd, bg=True)
    p1 = e3.os.process.Run(short_cmd, bg=True)

    try:
        assert (
            wait_for_objects(
                [int(p0.internal._handle), int(p1.internal._handle)], timeout=2
            )
            == 1
        ), "process 1 was expected"
    finally:
        p0.kill()
        p1.kill()

    p0 = e3.os.process.Run(long_cmd, bg=True)
    p1 = e3.os.process.Run(short_cmd, bg=True)

    try:
        assert (
            wait_for_objects(
                [int(p0.internal._handle), int(p1.internal._handle)],
                timeout=2,
                wait_for_all=True,
            )
            is None
        ), "timeout expected"
    finally:
        p0.kill()
        p1.kill()

    p0 = e3.os.process.Run(short_cmd, bg=True)
    p1 = e3.os.process.Run(short_cmd, bg=True)
    try:
        assert (
            wait_for_objects(
                [int(p0.internal._handle), int(p1.internal._handle)],
                timeout=0,
                wait_for_all=True,
            )
            is not None
        ), "no timeout expected"
    finally:
        p0.kill()
        p1.kill()
