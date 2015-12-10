from __future__ import absolute_import

import e3.os
from e3.platform_db import PLATFORM_INFO, BUILD_TARGETS


class Platform(e3.os.platform.Immutable):
    """Class that allow user to retrieve os/cpu specific information.

    :ivar cpu: CPU information
    :ivar os: Operating system information
    :ivar is_hie: True if the system is a high integrity system
    :ivar platform: platform name. Ex: x86-linux
    :ivar triplet:  GCC target
    :ivar machine:  machine name
    :ivar domain:   domain name
    :ivar is_host:  True if this is not a cross context
    :ivar is_virtual: Set to True if the current system is a virtual one.
        Currently set only for Solaris containers, Linux VMware and Windows on
        VMware.
    :ivar is_default: True if the platform is the default one
    """

    default_arch = None
    system_info = e3.os.platform.SystemInfo

    __slots__ = ["cpu", "os", "is_hie", "platform", "triplet",
                 "machine", "domain", "is_host",
                 "is_default"]

    def __init__(self, platform_name=None, version=None, is_host=False,
                 machine=None, compute_default=False, mode=None):
        """Initialize a Platform.

        :param platform_name: if None or empty then automatically detect
            current platform (native). Otherwise should be a valid platform
            string.
        :type platform_name: str | None
        :param version:  if None, assume default OS version or find it
            automatically (native case only). Otherwise should be a valid
            version string.
        :type version: str | None
        :param is_host:  if True the system is not a cross one. Default is
            False except if a platform_name is not specified or if the
            platform_name is equal to the automatically detected one.
        :type is_host: bool
        :param machine: name of the machine
        :type machine: str | None
        :param compute_default: if True compute the default Arch for the
            current machine (this parameter is for internal purpose only).
        :param mode: an os mode (ex: rtp for vxworks)
        :type mode: str | None
        """
        # normalize arguments
        if not version:
            version = e3.os.platform.UNKNOWN
        if not machine or machine == e3.os.platform.UNKNOWN:
            machine = ''
        if not mode:
            mode = e3.os.platform.UNKNOWN

        def set_attr(name, value):
            object.__setattr__(self, name, value)

        set_attr("cpu", None)
        set_attr("os", None)
        set_attr("platform", platform_name)

        # Initialize default arch class variable
        if self.default_arch is None and not compute_default:
            self.__class__.default_arch = Platform(compute_default=True)

        set_attr("is_default", False)
        set_attr("machine", machine)
        set_attr("is_hie", False)
        set_attr("domain", e3.os.platform.UNKNOWN)

        if compute_default:
            default_platform = self.system_info.platform()
        else:
            default_platform = self.default_arch.platform

        if self.platform is None or self.platform in ('', 'default'):
            set_attr("platform", default_platform)

        if self.platform == default_platform or is_host:
            set_attr("is_host", True)

            # This is host so we can guess the machine name and domain
            machine, domain = self.system_info.hostname()
            set_attr("machine", machine)
            set_attr("domain", domain)
            set_attr("is_default", self.platform == default_platform)

        else:
            set_attr("is_host", False)
            # This is a target name. Sometimes it's suffixed by the host os
            # name. If the name is not a key in config.platform_info try to
            # to find a valid name by suppressing -linux, -solaris or -windows
            if self.platform not in PLATFORM_INFO:
                for suffix in ('-linux', '-solaris', '-windows'):
                    if self.platform.endswith(suffix):
                        set_attr("platform", self.platform[:-len(suffix)])
                        break

        # Fill other attributes
        pi = PLATFORM_INFO[self.platform]
        set_attr("cpu",
                 e3.os.platform.CPU(
                     pi['cpu'], pi.get('endian', None), self.is_host))
        set_attr("os",
                 e3.os.platform.OS(
                     pi['os'], self.is_host, version=version, mode=mode))
        set_attr("is_hie", pi['is_hie'])

        # Find triplet
        set_attr("triplet", None)
        set_attr("triplet",
                 BUILD_TARGETS[self.platform]['name'] % self.to_dict())

    @property
    def is_virtual(self):
        """Check if we are on a virtual system.

        :return: True if the system represented by Arch is a virtual machine
        :rtype: bool
        """
        if not self.is_host:
            return False
        return self.system_info.is_virtual()

    def to_dict(self):
        """Export os and cpu variables as os_{var} and cpu_{var}.

        :return: a dictionary representing the current Arch instance
        :rtype: dict
        """
        str_dict = self.as_dict()
        str_dict['is_virtual'] = self.is_virtual

        for key, var in self.os.as_dict().iteritems():
            str_dict["os_" + key] = var
        for key, var in self.cpu.as_dict().iteritems():
            str_dict["cpu_" + key] = var
        del str_dict['os']
        del str_dict['cpu']
        return str_dict

    def __str__(self):
        """Return a representation string of the object."""
        result = "platform: %(platform)s\n" \
                 "machine:  %(machine)s\n" \
                 "is_hie:   %(is_hie)s\n" \
                 "is_host:  %(is_host)s\n" \
                 "is_virtual: %(is_virtual)s\n" \
                 "triplet:  %(triplet)s\n" \
                 "domain:   %(domain)s\n" \
                 "OS\n" \
                 "   name:          %(os_name)s\n" \
                 "   version:       %(os_version)s\n" \
                 "   exeext:        %(os_exeext)s\n" \
                 "   dllext:        %(os_dllext)s\n" \
                 "   is_bareboard:  %(os_is_bareboard)s\n" \
                 "CPU\n" \
                 "   name:   %(cpu_name)s\n" \
                 "   bits:   %(cpu_bits)s\n" \
                 "   endian: %(cpu_endian)s\n" \
                 "   cores:  %(cpu_cores)s" % self.to_dict()
        return result