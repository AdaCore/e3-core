"""Module to retrieve information about the current system."""

from __future__ import annotations

import sys
from pathlib import Path
from platform import machine

from psutil import cpu_count, virtual_memory

import e3.log

logger = e3.log.getLogger("sysinfo")


class SysInfo:
    """Class to get information about the current system."""

    def __init__(self) -> None:
        """Initialize the SysInfo class."""
        self.__cpu_model: str | None = None

    @property
    def cpu_model(self) -> str:
        """Get the current CPU model.

        This function only support Linux and Windows.

        For ARM Linux, the returned string format is:

            ARM <CPU IMPLEMENTER> <CPU PART>

         <CPU IMPLEMENTER> and <CPU PART> are hexadecimal values.

        :return: The processor model, or "unknown" in case of an error.
        """
        if self.__cpu_model:
            return self.__cpu_model

        try:
            if sys.platform == "linux":
                if machine().lower().startswith(("arm", "aarch64")):
                    self.__cpu_model = f"ARM {self.__get_linux_arm_cpu_model()}"
                else:
                    self.__cpu_model = self.__get_linux_generic_cpu_model()
            elif sys.platform == "win32":
                self.__cpu_model = self.__get_windows_cpu_model()

        # We catch a blind exception because this function should never failed.
        except Exception as err:  # noqa: BLE001
            logger.debug(f"An exception occurs: {err}")

        return self.__cpu_model or "unknown"

    @property
    def physical_cores(self) -> int:
        """Get the number of physical cores of the current CPU.

        :return: The number of cores of the current CPU or 0 if undertermined.
        """
        return cpu_count(logical=False) or 0

    @property
    def logical_cores(self) -> int:
        """Get the number of logical cores of the current CPU.

        :return: The number of logical CPUs or 0 if undertermined.
        """
        return cpu_count(logical=True) or 0

    @property
    def total_ram_gb(self) -> int:
        """Get the amount of RAM.

        :return: The amount of RAM in GiB.
        """
        return int(virtual_memory().total / (1024**3))

    def __get_linux_arm_cpu_model(self) -> str:
        """Get the ARM CPU model for a linux machine.

        '/proc/cpuinfo' on ARM linux doesn't contains directly the model name. This
        method search for 'CPU implementer' and 'CPU part' field and return the value
        as provided (in hexadecimal).

        :return: The model name with the following format
            '<CPU implementer> [<CPU part>]' or 'unknown' if no information is provided.
        """
        cpuinfo_path = Path("/proc", "cpuinfo")
        if not cpuinfo_path.exists():
            return "unknown"

        cpu_implementer: str = ""
        cpu_part: str = ""

        with cpuinfo_path.open() as cpuinfo_file:
            for line in cpuinfo_file:
                if cpu_implementer and cpu_part:
                    break

                if line.startswith("CPU implementer"):
                    cpu_implementer = line.split(":", 1)[1].strip()
                if line.startswith("CPU part"):
                    cpu_part = line.split(":", 1)[1].strip()

            if not cpu_implementer:
                return "unknown"
            if not cpu_part:
                return cpu_implementer
            return f"{cpu_implementer} {cpu_part}"

    def __get_linux_generic_cpu_model(self) -> str:
        """Get the CPU model for a linux machine.

        This function search for the 'model name' field in '/proc/cpuinfo'

        :return: The model name as provided by '/proc/cpuinfo'
        """
        cpuinfo_path = Path("/proc", "cpuinfo")
        if not cpuinfo_path.exists():
            return "unknown"

        res = None

        with cpuinfo_path.open() as cpuinfo_file:
            for line in cpuinfo_file:
                if line.startswith("model name"):
                    res = line.split(":", 1)[1].strip()
                    break

        return res or "unknown"

    def __get_windows_cpu_model(self) -> str:  # os-specific
        """Get the CPU model for a windows machine.

        The method return the CPU model as provided by the Windows registry.

        :return; The model name.
        """
        # We don't want this import to be at the top level since it may not exists if
        # the current OS is not windows.
        import winreg  # noqa: PLC0415

        key = winreg.OpenKey(  # type: ignore[attr-defined]
            winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
            r"Hardware\Description\System\CentralProcessor\0",
        )
        res = winreg.QueryValueEx(key, "ProcessorNameString")[0]  # type: ignore[attr-defined]
        winreg.CloseKey(key)  # type: ignore[attr-defined]
        return res
