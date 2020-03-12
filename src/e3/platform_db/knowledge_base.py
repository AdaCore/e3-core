"""Knowledge base for CPU, OS, and Platform informations.

Note that even if this is pure data this is not stored as a yaml. This
knowledge base is very often read and the cost of parsing the data can
be significant in some context.
"""


CPU_INFO = {
    "aarch64": {"endian": "little", "bits": 64},
    "arm": {"endian": "little", "bits": 32},
    "avr": {"endian": "little", "bits": 16},
    "powerpc": {"endian": "big", "bits": 32},
    "powerpc64": {"endian": "big", "bits": 64},
    "sparc": {"endian": "big", "bits": 32},
    "sparc64": {"endian": "big", "bits": 64},
    "x86": {"endian": "little", "bits": 32},
    "x86_64": {"endian": "little", "bits": 64},
}

OS_INFO = {
    "aix": {"is_bareboard": False, "version": "5.2", "exeext": "", "dllext": ".so"},
    "darwin": {
        "is_bareboard": False,
        "version": "9.6.0",
        "exeext": "",
        "dllext": ".dylib",
    },
    "freebsd": {
        "is_bareboard": False,
        "version": "unknown",
        "exeext": "",
        "dllext": ".so",
    },
    "openbsd": {
        "is_bareboard": False,
        "version": "unknown",
        "exeext": "",
        "dllext": ".so",
    },
    "netbsd": {
        "is_bareboard": False,
        "version": "unknown",
        "exeext": "",
        "dllext": ".so",
    },
    "dragonfly": {
        "is_bareboard": False,
        "version": "unknown",
        "exeext": "",
        "dllext": ".so",
    },
    "ios": {
        "is_bareboard": False,
        "version": "unknown",
        "exeext": "",
        "dllext": ".dylib",
    },
    "linux": {
        "is_bareboard": False,
        "version": "unknown",
        "exeext": "",
        "dllext": ".so",
    },
    "solaris": {"is_bareboard": False, "version": "2.8", "exeext": "", "dllext": ".so"},
    "windows": {
        "is_bareboard": False,
        "version": "XP",
        "exeext": ".exe",
        "dllext": ".dll",
    },
    "none": {"is_bareboard": True, "version": "unknown", "exeext": "", "dllext": ""},
}

PLATFORM_INFO = {
    "aarch64-elf": {"cpu": "aarch64", "os": "none", "is_hie": True},
    "aarch64-ios": {"cpu": "aarch64", "os": "ios", "is_hie": False},
    "aarch64-linux": {"cpu": "aarch64", "os": "linux", "is_hie": False},
    "arm-android": {"cpu": "arm", "os": "android", "is_hie": False},
    "arm-elf": {"cpu": "arm", "os": "none", "is_hie": True},
    "arm-ios": {"cpu": "arm", "os": "ios", "is_hie": False},
    "avr-elf": {"cpu": "avr", "os": "none", "is_hie": True},
    "arm-linux": {"cpu": "arm", "os": "linux", "is_hie": False, "endian": "little"},
    "ppc-aix": {"cpu": "powerpc", "os": "aix", "is_hie": False},
    "ppc-linux": {"cpu": "powerpc", "os": "linux", "is_hie": False},
    "raspberrypi-linux": {
        "cpu": "arm",
        "os": "linux",
        "is_hie": False,
        "endian": "little",
    },
    "sparc64-solaris": {"cpu": "sparc64", "os": "solaris", "is_hie": False},
    "sparc-solaris": {"cpu": "sparc", "os": "solaris", "is_hie": False},
    "x86_64-linux": {"cpu": "x86_64", "os": "linux", "is_hie": False},
    "x86_64-darwin": {"cpu": "x86_64", "os": "darwin", "is_hie": False},
    "x86-freebsd": {"cpu": "x86", "os": "freebsd", "is_hie": False},
    "x86-openbsd": {"cpu": "x86", "os": "openbsd", "is_hie": False},
    "x86-netbsd": {"cpu": "x86", "os": "netbsd", "is_hie": False},
    "x86-dragonfly": {"cpu": "x86", "os": "dragonfly", "is_hie": False},
    "x86_64-freebsd": {"cpu": "x86_64", "os": "freebsd", "is_hie": False},
    "x86_64-openbsd": {"cpu": "x86_64", "os": "openbsd", "is_hie": False},
    "x86_64-netbsd": {"cpu": "x86_64", "os": "netbsd", "is_hie": False},
    "x86_64-dragonfly": {"cpu": "x86_64", "os": "dragonfly", "is_hie": False},
    "x86-linux": {"cpu": "x86", "os": "linux", "is_hie": False},
    "x86-solaris": {"cpu": "x86", "os": "solaris", "is_hie": False},
    "x86_64-solaris": {"cpu": "x86_64", "os": "solaris", "is_hie": False},
    "x86-windows": {"cpu": "x86", "os": "windows", "is_hie": False},
    "x86_64-windows": {"cpu": "x86_64", "os": "windows", "is_hie": False},
    "x86_64-windows64": {"cpu": "x86_64", "os": "windows", "is_hie": False},
}

BUILD_TARGETS = {
    "aarch64-elf": {"name": "aarch64-elf"},
    "aarch64-ios": {"name": "aarch64-apple-darwin"},
    "aarch64-linux": {"name": "aarch64-linux-gnu"},
    "arm-android": {"name": "arm-linux-androideabi"},
    "arm-elf": {"name": "arm-eabi"},
    "arm-ios": {"name": "arm-apple-darwin10"},
    "avr-elf": {"name": "avr"},
    "arm-linux": {"name": "arm-linux-gnueabi"},
    "ppc-aix": {"name": "powerpc-ibm-aix%(os_version)s.0.0"},
    "ppc-linux": {"name": "powerpc-generic-linux-gnu"},
    "raspberrypi-linux": {"name": "arm-linux-gnueabihf"},
    "sparc64-solaris": {"name": "sparc64-sun-solaris%(os_version)s"},
    "sparc-solaris": {"name": "sparc-sun-solaris%(os_version)s"},
    "x86_64-linux": {"name": "x86_64-pc-linux-gnu"},
    "x86_64-darwin": {"name": "x86_64-apple-darwin%(os_version)s"},
    "x86-freebsd": {"name": "i386-pc-freebsd%(os_version)s"},
    "x86-openbsd": {"name": "i386-pc-openbsd%(os_version)s"},
    "x86-netbsd": {"name": "i386-pc-netbsd%(os_version)s"},
    "x86-dragonfly": {"name": "i386-pc-dragonfly%(os_version)s"},
    "x86_64-freebsd": {"name": "x86_64-pc-freebsd%(os_version)s"},
    "x86_64-openbsd": {"name": "x86_64-pc-openbsd%(os_version)s"},
    "x86_64-netbsd": {"name": "x86_64-pc-netbsd%(os_version)s"},
    "x86_64-dragonfly": {"name": "x86_64-pc-dragonfly%(os_version)s"},
    "x86-linux": {"name": "i686-pc-linux-gnu"},
    "x86-solaris": {"name": "i686-pc-solaris%(os_version)s"},
    "x86_64-solaris": {"name": "x86_64-sun-solaris%(os_version)s"},
    "x86-windows": {"name": "i686-pc-mingw32"},
    "x86_64-windows": {"name": "x86_64-pc-mingw32"},
    "x86_64-windows64": {"name": "x86_64-w64-mingw32"},
}

# The following table is used to guess a product name from the output of
# uname on the host. Users of this data are expected to match the specified
# regular expressions against that output to find a matching key. Order is
# not significant so if a traversal matches multiple entries the one matched
# is undefined. It is critical therefore that the supplied expressions match
# only the intended product and no other values of uname potentially output
# by a different host. IMPORTANT: Systems that can be only used as target in
# cross context should not be added to that table.

HOST_GUESS = {
    # platform : OS (uname[0]), machine (uname[1]), proc (uname[4 or 5])
    "ppc-aix": {"os": "AIX", "cpu": None},
    "x86_64-darwin": {"os": "Darwin", "cpu": "i386"},
    "x86-freebsd": {"os": "FreeBSD", "cpu": "i386"},
    "x86-openbsd": {"os": "OpenBSD", "cpu": None},
    "x86-netbsd": {"os": "NetBSD", "cpu": None},
    "x86-dragonfly": {"os": "DragonFly", "cpu": None},
    "x86_64-freebsd": {"os": "FreeBSD", "cpu": "amd64"},
    "x86_64-openbsd": {"os": "OpenBSD", "cpu": None},
    "x86_64-netbsd": {"os": "NetBSD", "cpu": None},
    "x86_64-dragonfly": {"os": "DragonFly", "cpu": None},
    "ppc-linux": {"os": "Linux", "cpu": "powerpc.*|ppc64"},
    "x86-linux": {"os": "Linux", "cpu": "i.86|pentium"},
    "x86_64-linux": {"os": "Linux", "cpu": "x86_64"},
    "sparc-solaris": {"os": "SunOS", "cpu": "sparc"},
    "x86-solaris": {"os": "SunOS", "cpu": "i386"},
    "x86-windows": {"os": "Windows", "cpu": None},
}
