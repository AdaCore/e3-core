"""Provides function to detect platform specific information."""
from __future__ import absolute_import
import platform
from collections import namedtuple

import re

import e3.log
from e3.platform_db import HOST_GUESS, CPU_INFO, OS_INFO

UNKNOWN = 'unknown'

Uname = namedtuple("Uname", ["system",
                             "node",
                             "release",
                             "version",
                             "machine",
                             "processor"])


class SystemInfo(object):
    """Gather info about the system.

    :cvar network_ifs: dictionary addressed by network interface name for which
        each value is the result of netifaces.ifaddresses function on the given
        interface
    :cvar linux_distrib: tuple of strings containing respectively the
        Linux distribution name and version.
    :cvar uname: instance of Uname namedtuple containing the result of
        ``uname`` system call.
    :cvar core_number: integer containing the number of processor cores on the
        machine
    :cvar nis_domain: host nis domain
    """
    network_ifs = None
    linux_distrib = None
    uname = None
    core_number = None
    nis_domain = None

    # Cache for SystemInfo methods
    _platform = None
    _os_version = None
    _is_virtual = None
    _hostname = None

    @classmethod
    def reset_cache(cls):
        """Reset SystemInfo cache."""
        cls.network_ifs = None
        cls.linux_distrib = None
        cls.uname = None
        cls.core_number = None
        cls._is_virtual = None
        cls._platform = None
        cls._os_version = None
        cls._hostname = None

    @classmethod
    def fetch_system_data(cls):
        """Fetch info from the host system.

        The function should be the only one that use system calls or programs
        to fetch information from the current system. Overriding this method
        should be enough for example for testing purposes as all the other
        methods use information retrieved in this function.

        The function should set all the class attributes described at the
        beginning of this class.
        """
        # Compute result of uname
        cls.uname = Uname(*platform.uname())

        # Fetch the linux release file
        if cls.uname.system == 'Linux':
            cls.linux_distrib = \
                platform.linux_distribution()
        else:
            cls.linux_distrib = None

        # Fetch network interfaces
        try:
            from netifaces import interfaces, ifaddresses, address_families
            # use string for address families instead of integers which are
            # system dependents
            cls.network_ifs = {itf: {address_families[k]: v
                                     for k, v in ifaddresses(itf).iteritems()}
                               for itf in interfaces()}
        except Exception:
            e3.log.debug('cannot get network info', exc_info=True)
            cls.network_ifs = None

        # Fetch core numbers. Note that the methods does not work
        # on AIX platform but we usually override manually that
        # setting anyway.
        cls.core_number = 1
        try:
            import multiprocessing
            cls.core_number = multiprocessing.cpu_count()
        except Exception:
            e3.log.debug('multiprocessing error', exc_info=True)
            try:
                import psutil
                cls.core_number = psutil.cpu_count()
            except Exception:
                e3.log.debug('psutil error', exc_info=True)
                pass

        cls.nis_domain = UNKNOWN
        try:
            import nis
            try:
                cls.nis_domain = nis.get_default_domain()
                if not cls.nis_domain:
                    cls.nis_domain = UNKNOWN
            except nis.error:
                e3.log.debug('nis error', exc_info=True)
                pass
        except ImportError:
            e3.log.debug('cannot import nis', exc_info=True)
            pass

    @classmethod
    def platform(cls):
        """Guess platform name.

        Internal function that guess base on uname system call the
        current platform

        :return: the platform name
        :rtype: str
        """
        if cls._platform is not None:
            return cls._platform

        if cls.uname is None:
            cls.fetch_system_data()

        result = [p for p, v in HOST_GUESS.iteritems()
                  if cls.uname.system == v['os'] and
                  (v['cpu'] is None or
                   re.match(v['cpu'], cls.uname.machine) or
                   re.match(v['cpu'], cls.uname.processor))]

        if result:
            result = result[0]
        else:
            result = UNKNOWN

        cls._platform = result
        return result

    @classmethod
    def os_version(cls):
        """Compute OS version information.

        :return: a tuple containing os version and kernel version
        :rtype: (str, str)
        """
        if cls._os_version is not None:
            return cls._os_version

        if cls.uname is None:
            cls.fetch_system_data()

        version = UNKNOWN
        kernel_version = UNKNOWN
        system = cls.uname.system

        if system == 'Darwin':
            version = cls.uname.release
        elif system == 'FreeBSD':
            version = re.sub('-.*', '', cls.uname.release)
        elif system == 'Linux':
            kernel_version = cls.uname.release
            distrib = cls.linux_distrib
            for name in ('red hat', 'ubuntu', 'debian', 'suse'):
                if name in distrib[0].lower():
                    version = '%s%s' % (
                        name.replace('red hat', 'rhES'),
                        distrib[1].split('.')[0])
                    if name == 'debian':
                        version = version.replace('/sid', '')
                        version = version.replace('wheezy', '7')
                    break
            if version == UNKNOWN:
                version = '%s%s' % (distrib[0].replace(' ', ''),
                                    distrib[1].split('.')[0])
        elif system == 'AIX':
            version = cls.uname.version + '.' + cls.uname.release
        elif system == 'SunOS':
            version = '2' + cls.uname.release[1:]
        elif system == 'Windows':
            version = cls.uname.release.replace('Server', '')
            kernel_version = cls.uname.version
            if version == 'Vista' and '64' in cls.uname.machine:
                version = 'Vista64'

        cls._os_version = (version, kernel_version)
        return version, kernel_version

    @classmethod
    def is_virtual(cls):
        """Check if current machine is virtual or not.

        :return: True if the machine is a virtual machine (Solaris zone,
            VmWare)
        :rtype: bool
        """
        if cls._is_virtual is not None:
            return cls._is_virtual

        if cls.uname is None:
            cls.fetch_system_data()

        result = False

        if cls.uname.system == 'SunOS' and \
                cls.uname.version == 'Generic_Virtual':
            result = True
        else:
            if cls.network_ifs is not None:
                for interface in cls.network_ifs.values():
                    for family in ('AF_LINK', 'AF_PACKET'):
                        if family in interface:
                            for el in interface[family]:
                                addr = el['addr'].lower()
                                if addr.startswith('00:0c:29') or \
                                        addr.startswith('00:50:56'):
                                    result = True
                                    break
                        if result:
                            break
                    if result:
                        break
        cls._is_virtual = result
        return result

    @classmethod
    def hostname(cls):
        """Get hostname and associated domain.

        :return: a tuple (hostname, domain)
        :rtype: (str, str)
        """
        if cls._hostname is not None:
            return cls._hostname

        if cls.uname is None:
            cls.fetch_system_data()

        # This is host so we can find the machine name using uname fields
        tmp = cls.uname.node.lower().split('.', 1)
        hostname = tmp[0]
        if len(tmp) > 1:
            domain = tmp[1]
        else:
            domain = cls.nis_domain
        cls._hostname = (hostname, domain)
        return cls._hostname


class Immutable(object):
    def __setattr__(self, name, value):
        msg = "'%s' has no attribute %s" % (self.__class__,
                                            name)
        raise AttributeError(msg)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return tuple(getattr(self, slot) for slot in self.__slots__) == \
            tuple(getattr(other, slot) for slot in self.__slots__)

    def __hash__(self):
        return hash(tuple(getattr(self, slot) for slot in self.__slots__))

    def __getstate__(self):
        return self.as_dict()

    def __setstate__(self, state):
        for s in self.__slots__:
            object.__setattr__(self, s, state[s])

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    def __str__(self):
        result = ["%s: %s" % (k, getattr(self, k)) for k in self.__slots__]
        return "\n".join(result)


class CPU(Immutable):
    """CPU attributes.

    :ivar name: string containing the cpu name
    :ivar bits: int representing the number of bits for the cpu or 'unknown'
    :ivar endian: 'big', 'little' or 'unknown'
    :ivar cores: int representing the number of cores
    """

    __slots__ = ["name", "bits", "endian", "cores"]

    def __init__(self, name, endian=None, compute_cores=False):
        """Initialize CPU instance.

        :param name: cpu name
        :type name: str
        :param endian: if not None override endianness default settings
        :type endian: str
        :param compute_cores: if True compute the number of cores
        :type compute_cores: bool
        """
        assert name in CPU_INFO, "invalid cpu name"
        set_attr = object.__setattr__
        set_attr(self, "name", name)
        set_attr(self, "bits", CPU_INFO[self.name]['bits'])
        set_attr(self, "endian", endian)
        set_attr(self, "cores", 1)

        if self.endian is None:
            set_attr(self, "endian", CPU_INFO[self.name]['endian'])
        if compute_cores:
            set_attr(self, "cores", SystemInfo.core_number)


class OS(Immutable):
    """OS attributes.

    :ivar name: os name
    :ivar version: string containing the os version
    :ivar exeext: default executable extension
    :ivar dllext: default shared library extension
    :ivar is_bareboard: True if the system is bareboard, False otherwise
    """

    __slots__ = ["name", "version", "exeext", "dllext", "is_bareboard", "mode"]

    def __init__(self, name, is_host=False, version=UNKNOWN, mode=UNKNOWN):
        """Initialize OS instance.

        :param name: os name
        :type name: str
        :param is_host: if True the OS instance is for the host system
        :type is_host: bool
        :param version: os version
        :type version: str | None
        :param mode: os mode
        :type mode: str | None
        """
        set_attr = object.__setattr__
        set_attr(self, "name", name)
        set_attr(self, "version", version)
        set_attr(self, "exeext", "")
        set_attr(self, "dllext", "")
        set_attr(self, "is_bareboard", False)
        set_attr(self, "kernel_version", None)
        set_attr(self, "mode", mode)

        set_attr(self, "is_bareboard",
                 OS_INFO[self.name]['is_bareboard'])
        set_attr(self, "exeext", OS_INFO[self.name]['exeext'])

        if self.name.startswith('vxworks') and self.mode == 'rtp':
            set_attr(self, "exeext", ".vxe")

        set_attr(self, "dllext", OS_INFO[self.name]['dllext'])

        # If version is not given by the user guess it or set it to the
        # default (cross case)
        if self.version == UNKNOWN:
            if is_host:
                version, kernel_version = SystemInfo.os_version()
                set_attr(self, "version", version)
                set_attr(self, "kernel_version", kernel_version)
            else:
                set_attr(self, "version", OS_INFO[self.name]['version'])
                set_attr(self, "kernel_version", UNKNOWN)
