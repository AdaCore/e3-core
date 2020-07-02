from __future__ import annotations

import collections
from typing import TYPE_CHECKING

import e3.os
import e3.os.platform
from e3.platform_db import get_knowledge_base

if TYPE_CHECKING:
    from typing import Any, Dict, Optional

KNOWLEDGE_BASE = get_knowledge_base()


# noinspection PyUnresolvedReferences
class Platform(
    collections.namedtuple(
        "Platform",
        [
            "cpu",
            "os",
            "is_hie",
            "platform",
            "triplet",
            "machine",
            "domain",
            "is_host",
            "is_default",
        ],
    )
):
    """Class that allow user to retrieve os/cpu specific information.

    Attributes are:

    - cpu: CPU information
    - os: Operating System information
    - is_hie: whether the system is a high integrity system
    - platform: the platform name, e.g. arm-elf-linux
    - triplet: the GCC target
    - machine: machine name
    - domain: domain name
    - is_host: True if the instance represent information for the current
        machine
    - is_default: True if the platform is the default one
    """

    default_arch: Optional[Platform] = None
    system_info = e3.os.platform.SystemInfo

    __slots__ = ()

    @classmethod
    def get(
        cls,
        platform_name: Optional[str] = None,
        version: Optional[str] = None,
        machine: Optional[str] = None,
        mode: Optional[str] = None,
        compute_default: bool = False,
    ) -> Platform:
        """Return a Platform object.

        :param platform_name: if None or empty then automatically detect
            current platform (native). Otherwise should be a valid platform
            string.
        :param version:  if None, assume default OS version or find it
            automatically (native case only). Otherwise should be a valid
            version string.
        :param machine: name of the machine
        :param compute_default: if True compute the default Arch for the
            current machine (this parameter is for internal purpose only).
        :param mode: an os mode (ex: rtp for vxworks)
        """
        # normalize arguments
        if not version:
            version = e3.os.platform.UNKNOWN
        if machine is None or machine == e3.os.platform.UNKNOWN:
            machine = ""
        if not mode:
            mode = e3.os.platform.UNKNOWN

        # Initialize default arch class variable
        if cls.default_arch is None and not compute_default:
            cls.default_arch = Platform.get(compute_default=True)

        is_default = False
        is_host = False
        domain = e3.os.platform.UNKNOWN

        if compute_default:
            default_platform = cls.system_info.platform()
        else:
            assert cls.default_arch is not None
            default_platform = cls.default_arch.platform

        # Check if the object correspond to the current machine and thus allow
        # us to compute some additional info automatically
        if platform_name in (None, "", "default"):
            platform_name = default_platform
            is_host = True
        if machine == cls.system_info.hostname()[0]:
            is_host = True

        if is_host:
            # This is host so we can guess the machine name and domain
            machine, domain = cls.system_info.hostname()
            is_default = platform_name == default_platform

        # Fill other attributes
        assert platform_name is not None
        pi = KNOWLEDGE_BASE.platform_info[platform_name]
        cpu = e3.os.platform.CPU.get(pi["cpu"], pi.get("endian", None), is_host)
        os = e3.os.platform.OS.get(pi["os"], is_host, version=version, mode=mode)
        is_hie = pi["is_hie"]

        # Find triplet
        triplet = KNOWLEDGE_BASE.build_targets[platform_name]["name"] % {
            "os_version": os.version
        }

        return cls(
            cpu,
            os,
            is_hie,
            platform_name,
            triplet,
            machine,
            domain,
            is_host,
            is_default,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export os and cpu variables as os_{var} and cpu_{var}.

        :return: a dictionary representing the current Arch instance
        """
        str_dict = self._asdict()

        for key, var in self.os.as_dict().items():
            str_dict["os_" + key] = var
        for key, var in self.cpu.as_dict().items():
            str_dict["cpu_" + key] = var
        del str_dict["os"]
        del str_dict["cpu"]
        return str_dict

    def __str__(self) -> str:
        """Return a representation string of the object."""
        result = (
            "platform: %(platform)s\n"
            "machine:  %(machine)s\n"
            "is_hie:   %(is_hie)s\n"
            "is_host:  %(is_host)s\n"
            "triplet:  %(triplet)s\n"
            "domain:   %(domain)s\n"
            "OS\n"
            "   name:          %(os_name)s\n"
            "   version:       %(os_version)s\n"
            "   exeext:        %(os_exeext)s\n"
            "   dllext:        %(os_dllext)s\n"
            "   is_bareboard:  %(os_is_bareboard)s\n"
            "CPU\n"
            "   name:   %(cpu_name)s\n"
            "   bits:   %(cpu_bits)s\n"
            "   endian: %(cpu_endian)s\n"
            "   cores:  %(cpu_cores)s" % self.to_dict()
        )
        return result
