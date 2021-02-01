"""Provides function to detect platform specific information."""
from __future__ import annotations

import os
import re
import sys
from collections import namedtuple
from platform import uname as platform_uname
from typing import TYPE_CHECKING

import e3.log
from e3.platform_db import get_knowledge_base


if TYPE_CHECKING:
    from typing import Any, Dict, Optional, Tuple

KNOWLEDGE_BASE = get_knowledge_base()

UNKNOWN = "unknown"

Uname = namedtuple(
    "Uname", ["system", "node", "release", "version", "machine", "processor"]
)


class SystemInfo:
    """Gather info about the system.

    :cvar uname: instance of Uname namedtuple containing the result of
        ``uname`` system call.
    :cvar core_number: integer containing the number of processor cores on the
        machine
    :cvar nis_domain: host nis domain
    """

    uname = None
    core_number = 1
    nis_domain = None
    ld_info = None

    # Cache for SystemInfo methods
    _platform: Optional[str] = None

    # _os_version is a tuple: os version, kernel version
    _os_version: Optional[Tuple[str, str]] = None

    # _hostname is a tuble: hostname, domain. Joining with a dot hostname and domain
    # represent the FQDN
    _hostname: Optional[Tuple[str, str]] = None

    @classmethod
    def reset_cache(cls) -> None:
        """Reset SystemInfo cache."""
        cls.uname = None
        cls.ld_info = None
        cls.core_number = 1
        cls._platform = None
        cls._os_version = None
        cls._hostname = None

    @classmethod
    def fetch_system_data(cls) -> None:
        """Fetch info from the host system.

        The function should be the only one that use system calls or programs
        to fetch information from the current system. Overriding this method
        should be enough for example for testing purposes as all the other
        methods use information retrieved in this function.

        The function should set all the class attributes described at the
        beginning of this class.
        """
        # Compute result of uname
        cls.uname = Uname(*platform_uname())

        # Fetch linux distribution info on linux OS
        if cls.uname.system == "Linux":  # linux-only
            import ld

            cls.ld_info = {
                "name": ld.name(),
                "major_version": ld.major_version(),
                "version": ld.version(),
            }

        # Fetch core numbers. Note that the methods does not work
        # on AIX platform but we usually override manually that
        # setting anyway.
        cls.core_number = 1
        try:
            import multiprocessing

            cls.core_number = multiprocessing.cpu_count()
        except Exception:  # defensive code
            e3.log.debug("multiprocessing error", exc_info=True)
            try:
                import psutil

                cls.core_number = psutil.cpu_count()
            except Exception:
                e3.log.debug("psutil error", exc_info=True)

        cls.nis_domain = UNKNOWN

        if sys.platform != "win32":  # windows: no cover
            try:
                import nis
            except ImportError:  # defensive code
                e3.log.debug("cannot import nis", exc_info=True)
                nis = None  # type: ignore

            if nis is not None:
                try:
                    cls.nis_domain = nis.get_default_domain()
                    if not cls.nis_domain:  # defensive code
                        cls.nis_domain = UNKNOWN
                except nis.error:  # defensive code
                    e3.log.debug("nis error", exc_info=True)

    @classmethod
    def platform(cls) -> str:
        """Guess platform name.

        Internal function that guess base on uname system call the
        current platform

        :return: the platform name
        """
        if cls._platform is not None:
            return cls._platform

        if cls.uname is None:
            cls.fetch_system_data()

        if TYPE_CHECKING:
            assert cls.uname is not None

        result = [
            p
            for p, v in KNOWLEDGE_BASE.host_guess.items()
            if cls.uname.system == v["os"]
            and (
                v["cpu"] is None
                or re.match(v["cpu"], cls.uname.machine)
                or re.match(v["cpu"], cls.uname.processor)
            )
        ]

        if result:
            cls._platform = result[0]
        else:  # defensive code
            cls._platform = UNKNOWN

        return cls._platform

    @classmethod
    def os_version(cls) -> Tuple[str, str]:
        """Compute OS version information.

        :return: a tuple containing os version and kernel version
        """
        if cls._os_version is not None:
            return cls._os_version

        if cls.uname is None:
            cls.fetch_system_data()

        if TYPE_CHECKING:
            assert cls.uname is not None
            assert cls.ld_info is not None

        version = UNKNOWN
        kernel_version = UNKNOWN
        system = cls.uname.system

        if system == "Darwin":  # darwin-only
            version = cls.uname.release
        elif system == "FreeBSD":  # bsd-only
            version = re.sub("-.*", "", cls.uname.release)
        elif system == "Linux":  # linux-only
            kernel_version = cls.uname.release
            name = cls.ld_info["name"].lower()
            if "redhat" in name or "red hat" in name:  # os-specific
                name = "rhES"
                version_number = cls.ld_info["major_version"]
            elif "suse" in name or "sles" in name:  # os-specific
                name = "suse"
                version_number = cls.ld_info["major_version"]
            elif "debian" in name:  # os-specific
                name = "debian"
                version_number = cls.ld_info["major_version"]
            else:  # os-specific
                version_number = cls.ld_info["version"]
            version = name + version_number
        elif system == "AIX":  # aix-only
            version = cls.uname.version + "." + cls.uname.release
        elif system == "SunOS":  # solaris-only
            version = "2" + cls.uname.release[1:]
        elif system == "Windows":  # windows-only
            version = cls.uname.release.replace("Server", "")
            kernel_version = cls.uname.version
            # Compute real underlying OS version. Starting with Windows 8.1
            # (6.3), the win32 function that returns the version may return
            # the wrong version depending on the application manifest. So
            # python will always return Windows 8 in that case.
            import ctypes

            class WinOSVersion(ctypes.Structure):
                _fields_ = [
                    ("dwOSVersionInfoSize", ctypes.c_ulong),
                    ("dwMajorVersion", ctypes.c_ulong),
                    ("dwMinorVersion", ctypes.c_ulong),
                    ("dwBuildNumber", ctypes.c_ulong),
                    ("dwPlatformId", ctypes.c_ulong),
                    ("szCSDVersion", ctypes.c_wchar * 128),
                    ("wServicePackMajor", ctypes.c_ushort),
                    ("wServicePackMinor", ctypes.c_ushort),
                    ("wSuiteMask", ctypes.c_ushort),
                    ("wProductType", ctypes.c_byte),
                    ("wReserved", ctypes.c_byte),
                ]

            def get_os_version() -> Tuple[None, None, None] | Tuple[float, int, bool]:
                """Return the real Windows kernel version.

                On recent version, the kernel version returned by the
                GetVersionEx Win32 function depends on the way the application
                has been compiled. Using RtlGetVersion kernel function ensure
                that the right version is returned.

                :return: the version as a table
                    (major.minor, build number, is_server)
                """
                os_version = WinOSVersion()
                os_version.dwOSVersionInfoSize = ctypes.sizeof(os_version)
                retcode = ctypes.windll.Ntdll.RtlGetVersion(  # type: ignore
                    ctypes.byref(os_version)
                )
                if retcode != 0:
                    return (None, None, None)

                return (
                    float(f"{os_version.dwMajorVersion}.{os_version.dwMinorVersion}"),
                    os_version.dwBuildNumber,
                    os_version.wProductType != 1,
                )

            effective_version, build_number, is_server = get_os_version()

            if effective_version is None or effective_version <= 6.2:
                if version == "Vista" and "64" in cls.uname.machine:  # os-specific
                    version = "Vista64"
            else:
                if effective_version == 6.3:
                    if is_server:
                        version = "2012R2"
                    else:
                        version = "8.1"
                elif effective_version == 10.0:
                    if TYPE_CHECKING:
                        assert build_number is not None
                    if is_server:
                        if build_number < 17763:
                            version = "2016"
                        else:
                            version = "2019"
                    else:
                        version = "10"

        cls._os_version = (version, kernel_version)
        return version, kernel_version

    @classmethod
    def hostname(cls) -> Tuple[str, str]:
        """Get hostname and associated domain.

        :return: a tuple (hostname, domain)
        """
        if cls._hostname is not None:
            return cls._hostname

        if cls.uname is None:
            cls.fetch_system_data()

        if TYPE_CHECKING:
            assert cls.uname is not None

        # This is host so we can find the machine name using uname fields
        tmp = cls.uname.node.lower().split(".", 1)
        hostname = tmp[0]
        if len(tmp) > 1:
            domain = tmp[1]
        else:
            domain = cls.nis_domain

        # Hostname can be overriden by E3_HOSTNAME env variable
        hostname = os.environ.get("E3_HOSTNAME", hostname)
        cls._hostname = (hostname, domain)
        return cls._hostname


class CPU(namedtuple("CPU", ["name", "bits", "endian", "cores"])):
    """Object representing a CPU.

    CPU attributes are:

    - name: [str] the CPU name
    - bits: number of bits for the cpu or 'unknown'
    - endian: big, little, or unknown
    - cores: number of cores available
    """

    __slots__ = ()

    def as_dict(self) -> Dict[str, Any]:
        return self._asdict()

    @classmethod
    def get(
        cls, name: str, endian: Optional[str] = None, compute_cores: bool = False
    ) -> CPU:
        """Initialize CPU instance.

        :param name: cpu name
        :param endian: if not None override endianness default settings
        :param compute_cores: if True compute the number of cores
        """
        assert name in KNOWLEDGE_BASE.cpu_info, "invalid cpu name"
        bits = KNOWLEDGE_BASE.cpu_info[name]["bits"]
        cores = 1

        if endian is None:
            endian = KNOWLEDGE_BASE.cpu_info[name]["endian"]
        if compute_cores:
            cores = SystemInfo.core_number

        return CPU(name, bits, endian, cores)


class OS(
    namedtuple(
        "OS",
        [
            "name",
            "version",
            "kernel_version",
            "exeext",
            "dllext",
            "is_bareboard",
            "mode",
        ],
    )
):
    """Object representing an OS.

    Attributes are:

    - name: the OS name
    - version: the OS version
    - kernel_version: the exact version of the kernel
    - exeext: the default executable extension (e.g. .exe on Windows)
    - dllext: the default shared library extension (e.g. .dll on Windows)
    - is_bareboard: whether the system has an OS or not.
    """

    __slots__ = ()

    def as_dict(self) -> Dict[str, Any]:
        return self._asdict()

    @classmethod
    def get(
        cls,
        name: str,
        is_host: bool = False,
        version: str = UNKNOWN,
        mode: str = UNKNOWN,
    ) -> OS:
        """Initialize OS instance.

        :param name: os name
        :param is_host: if True the OS instance is for the host system
        :param version: os version
        :param mode: os mode
        """
        is_bareboard = KNOWLEDGE_BASE.os_info[name]["is_bareboard"]
        if name.startswith("vxworks") and mode == "rtp":
            exeext = ".vxe"
        else:
            exeext = KNOWLEDGE_BASE.os_info[name]["exeext"]

        dllext = KNOWLEDGE_BASE.os_info[name]["dllext"]

        # If version is not given by the user guess it or set it to the
        # default (cross case)
        if version == UNKNOWN:
            if is_host:
                version, kernel_version = SystemInfo.os_version()
            else:
                version = KNOWLEDGE_BASE.os_info[name]["version"]
                kernel_version = UNKNOWN
        else:
            kernel_version = UNKNOWN
        return OS(name, version, kernel_version, exeext, dllext, is_bareboard, mode)
