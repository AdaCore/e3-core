"""Provides function to detect platform specific information."""
from __future__ import absolute_import
from platform import uname as platform_uname
from collections import namedtuple
import ld

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
    :cvar uname: instance of Uname namedtuple containing the result of
        ``uname`` system call.
    :cvar core_number: integer containing the number of processor cores on the
        machine
    :cvar nis_domain: host nis domain
    """

    network_ifs = None
    uname = None
    core_number = None
    nis_domain = None
    ld_info = None

    # Cache for SystemInfo methods
    _platform = None
    _os_version = None
    _is_virtual = None
    _hostname = None

    @classmethod
    def reset_cache(cls):
        """Reset SystemInfo cache."""
        cls.network_ifs = None
        cls.uname = None
        cls.ld_info = None
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
        cls.uname = Uname(*platform_uname())

        # Fetch linux distribution info on linux OS
        if cls.uname.system == 'Linux':
            cls.ld_info = {'name': ld.name(),
                           'major_version': ld.major_version(),
                           'version': ld.version()}

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
        except ImportError:
            e3.log.debug('cannot import nis', exc_info=True)
            nis = None

        if nis is not None:
            try:
                cls.nis_domain = nis.get_default_domain()
                if not cls.nis_domain:
                    cls.nis_domain = UNKNOWN
            except nis.error:
                e3.log.debug('nis error', exc_info=True)
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
            name = cls.ld_info['name'].lower()
            if 'redhat' in name:
                name = 'rhES'
                version_number = cls.ld_info['major_version']
            elif 'suse' in name:
                name = 'suse'
                version_number = cls.ld_info['major_version']
            elif 'debian' in name:
                name = 'debian'
                version_number = cls.ld_info['major_version']
            else:
                version_number = cls.ld_info['version']
            version = name + version_number
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


class CPU(namedtuple('CPU', ['name', 'bits', 'endian', 'cores'])):
    """Object representing a CPU.

    CPU attributes are:

    - name: [str] the CPU name
    - bits: number of bits for the cpu or 'unknown'
    - endian: big, little, or unknown
    - cores: number of cores available
    """

    __slots__ = ()

    def as_dict(self):
        return self._asdict()

    @classmethod
    def get(cls, name, endian=None, compute_cores=False):
        """Initialize CPU instance.

        :param name: cpu name
        :type name: str
        :param endian: if not None override endianness default settings
        :type endian: str
        :param compute_cores: if True compute the number of cores
        :type compute_cores: bool
        """
        assert name in CPU_INFO, "invalid cpu name"
        bits = CPU_INFO[name]['bits']
        cores = 1

        if endian is None:
            endian = CPU_INFO[name]['endian']
        if compute_cores:
            cores = SystemInfo.core_number

        return CPU(name, bits, endian, cores)


class OS(namedtuple('OS', ['name', 'version', 'kernel_version', 'exeext',
                           'dllext', 'is_bareboard', 'mode'])):
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

    def as_dict(self):
        return self._asdict()

    @classmethod
    def get(cls, name, is_host=False, version=UNKNOWN, mode=UNKNOWN):
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
        is_bareboard = OS_INFO[name]['is_bareboard']
        if name.startswith('vxworks') and mode == 'rtp':
            exeext = '.vxe'
        else:
            exeext = OS_INFO[name]['exeext']

        dllext = OS_INFO[name]['dllext']

        # If version is not given by the user guess it or set it to the
        # default (cross case)
        if version == UNKNOWN:
            if is_host:
                version, kernel_version = SystemInfo.os_version()
            else:
                version = OS_INFO[name]['version']
                kernel_version = UNKNOWN
        else:
            kernel_version = UNKNOWN
        return OS(name, version, kernel_version, exeext,
                  dllext, is_bareboard, mode)
