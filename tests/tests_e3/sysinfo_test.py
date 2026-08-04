"""Tests e3.sysinfo."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from e3.fs import sync_tree
from e3.sysinfo import SysInfo

if TYPE_CHECKING:
    from collections.abc import Generator


# We register the original Path class since we will mock it multiple time in this
# test.
ORIGINAL_PATH = Path


def test_sysinfo_cpu_cores() -> None:
    """Test SysInfo.physical_cores and SysInfo.logical_cores."""
    logical_cores = 10
    physical_cores = 1

    def mock_cpu_count(logical: bool) -> int:
        """Mock psutils.cpu_count.

        :param logical: Change the return value depending of its value.
        :return: 10 if logical is True, otherwise 1.
        """
        return logical_cores if logical else physical_cores

    with patch("e3.sysinfo.cpu_count", side_effect=mock_cpu_count):
        assert SysInfo().physical_cores == physical_cores
    with patch("e3.sysinfo.cpu_count", side_effect=mock_cpu_count):
        assert SysInfo().logical_cores == logical_cores


def test_sysinfo_total_ram_gb() -> None:
    """Test SysInfo.total_ram_gb."""
    expected_total_ram_gb = 8

    def mock_virtual_memory() -> int:
        """Mock psutils.virtual_memory."""

        class VirtualMemoryMocker:
            total = expected_total_ram_gb * 1024**3

        return VirtualMemoryMocker()

    with patch("e3.sysinfo.virtual_memory", side_effect=mock_virtual_memory):
        assert SysInfo().total_ram_gb == expected_total_ram_gb


def mock_path_raise_exception(*args: object, **kwargs: object) -> Path:
    """Mock pathlib.Path to generate an exception.

    :raises: OSError.
    """
    # Delete the argument to make Ruff happy
    del args
    del kwargs
    msg = "Sad"
    raise OSError(msg)


def mock_cpuinfo_file_doesnt_exist(*args: str, **kwargs: object) -> Path:
    """Provide a /proc/cpuinfo path that doesn't exist.

    See pathlib.Path.__init__ for parameters details.
    """
    if args == ("/proc", "cpuinfo"):
        return Path.cwd() / "file_doesnt_exist"
    return ORIGINAL_PATH(*args, **kwargs)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
def test_sysinfo_generic_cpu_model() -> None:
    """Test the human readble model retrieval for generic CPUs."""
    # First we have to synchronize our working dir with the data needed for this test.
    sync_tree(Path(__file__).parent / __file__.replace(".py", ""), Path.cwd())

    def mock_cpuinfo(*args: str, **kwargs: object) -> Path:
        """Provide a /proc/cpuinfo suitable for generic CPU.

        See pathlib.Path.__init__ for parameters details.
        """
        if args == ("/proc", "cpuinfo"):
            return Path.cwd() / "generic_cpuinfo"
        return ORIGINAL_PATH(*args, **kwargs)

    with patch("e3.sysinfo.Path", side_effect=mock_cpuinfo):
        sysinfo = SysInfo()
        assert sysinfo.cpu_model == "Intel i7"
        # Try again for coverage purpose: Since the code read a file, the result is
        # cached.
        assert sysinfo.cpu_model == "Intel i7"

    with patch("e3.sysinfo.Path", side_effect=mock_cpuinfo_file_doesnt_exist):
        assert SysInfo().cpu_model == "unknown"

    with patch("e3.sysinfo.Path", side_effect=mock_path_raise_exception):
        assert SysInfo().cpu_model == "unknown"


@pytest.fixture
def arm_sysinfo() -> Generator[None, None, None]:
    """Force e3.sysinfo to run the ARM specific code."""
    with patch("e3.sysinfo.machine", side_effect=lambda: "arm"):
        yield


# Ignore Ruff ARG001 (not used args) since arm_sysinfo is a pytests fixture used to
# mock the platform.machine() function for e3.sysinfo.
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
def test_sysinfo_arm_cpu_model(arm_sysinfo: None) -> None:  # noqa: ARG001
    """Test the human readble model retrieval for ARM CPUs."""
    # First we have to synchronize our working dir with the data needed for this test.
    sync_tree(Path(__file__).parent / __file__.replace(".py", ""), Path.cwd())

    def mock_full_cpuinfo(*args: str, **kwargs: object) -> Path:
        """Provide a /proc/cpuinfo suitable for ARM with full information inside.

        See pathlib.Path.__init__ for parameters details.
        """
        if args == ("/proc", "cpuinfo"):
            return Path.cwd() / "arm_cpuinfo_full"
        return ORIGINAL_PATH(*args, **kwargs)

    with patch("e3.sysinfo.Path", side_effect=mock_full_cpuinfo):
        assert SysInfo().cpu_model == "ARM 0x41 0xd4f"

    def mock_cpuinfo_no_cpu_part(*args: str, **kwargs: object) -> Path:
        """Provide a /proc/cpuinfo path suitable for ARM without CPU part field.

        See pathlib.Path.__init__ for parameters details.
        """
        if args == ("/proc", "cpuinfo"):
            return Path.cwd() / "arm_cpuinfo_no_cpu_part"
        return ORIGINAL_PATH(*args, **kwargs)

    with patch("e3.sysinfo.Path", side_effect=mock_cpuinfo_no_cpu_part):
        assert SysInfo().cpu_model == "ARM 0x41"

    def mock_cpuinfo_no_cpu_implementer(*args: str, **kwargs: object) -> Path:
        """Provide a /proc/cpuinfo path suitable for ARM without CPU implementer field.

        See pathlib.Path.__init__ for parameters details.
        """
        if args == ("/proc", "cpuinfo"):
            return Path.cwd() / "arm_cpuinfo_no_cpu_implementer"
        return ORIGINAL_PATH(*args, **kwargs)

    with patch("e3.sysinfo.Path", side_effect=mock_cpuinfo_no_cpu_implementer):
        assert SysInfo().cpu_model == "ARM unknown"

    with patch("e3.sysinfo.Path", side_effect=mock_cpuinfo_file_doesnt_exist):
        assert SysInfo().cpu_model == "ARM unknown"

    with patch("e3.sysinfo.Path", side_effect=mock_path_raise_exception):
        assert SysInfo().cpu_model == "unknown"
