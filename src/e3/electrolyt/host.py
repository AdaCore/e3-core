from __future__ import annotations

from typing import TYPE_CHECKING
import yaml

from e3.env import BaseEnv

if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional


class Host(BaseEnv):
    """Represent an host from the host database.

    See e3.env.BaseEnv
    """

    def __init__(
        self, hostname: str, platform: str, version: str, **kwargs: Any
    ) -> None:
        """Initialize an host entry.

        :param hostname: host name
        :param platform: platform name (see e3.platform)
        :param version: platform version (usually OS version)
        :param kwargs: additional user defined data. each key from the data
            dict is accessible like a regular attribute.
        """
        super().__init__()
        self.set_build(name=str(platform), version=str(version), machine=str(hostname))
        self._instance.update(kwargs)


class HostDB:
    """Host database.

    :ivar hosts: dict indexed by host name
    """

    def __init__(self, filename: Optional[str] = None):
        """Initialize a host database.

        :param filename: if not None, initialize the database from a yaml
            file. See HostDB.load_yaml_db method for details about the expected
            format
        """
        self.hosts: Dict[str, Host] = {}

        if filename is not None:
            self.load_yaml_db(filename)

    @property
    def hostnames(self) -> List[str]:
        """Return the current list of host names.

        :return: a list of hostnames
        """
        return list(self.hosts.keys())

    def add_host(self, hostname: str, platform: str, version: str, **data: Any) -> None:
        """Add/Update a host entry.

        :param hostname: host name
        :param platform: platform name (see e3.platform)
        :param version: platform/OS version
        :param data: additional host information
        """
        self.hosts[hostname] = Host(hostname, platform, version, **data)

    def load_yaml_db(self, filename: str) -> None:
        """Load a yaml configuration file.

        The yaml file should be a dictionaty indexed by host name. Each entry
        should be a dictionary containing at least the following two keys:

        * build_platform: the platform name
        * build_os_version: the platform/os version

        Additional keys for a host entry will be considered as additional data

        :param filename: path the yaml file
        """
        with open(filename) as fd:
            content = yaml.safe_load(fd)

        for hostname, hostinfo in content.items():
            result = {}
            for key in hostinfo:
                if key not in ("build_platform", "build_os_version"):
                    result[key] = hostinfo[key]
            platform = hostinfo["build_platform"]
            version = hostinfo["build_os_version"]
            self.add_host(hostname, platform, version, **result)

    def __getitem__(self, key: str) -> Host:
        return self.hosts[key]

    def get(self, key: str, default: Optional[Host] = None) -> Optional[Host]:
        """Return the Host named ``key`` of ``default``.

        :param key: host name
        :param default: default value to return if not found
        """
        return self.hosts.get(key, default)
