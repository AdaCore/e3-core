from __future__ import absolute_import, division, print_function

import yaml
from e3.env import BaseEnv


class Host(BaseEnv):
    """Represent an host from the host database.

    See e3.env.BaseEnv
    """

    def __init__(self,
                 hostname,
                 platform,
                 version,
                 **kwargs):
        """Initialize an host entry.

        :param hostname: host name
        :type hostname: str
        :param platform: platform name (see e3.platform)
        :type platform: str
        :param version: platform version (usually OS version)
        :type version: str
        :param kwargs: additional user defined data. each key from the data
            dict is accesiible like a regular attribute.
        :type kwargs: dict
        """
        BaseEnv.__init__(self)
        self.set_build(name=str(platform),
                       version=str(version),
                       machine=str(hostname))
        self._instance.update(kwargs)


class HostDB(object):
    """Host database.

    :ivar hosts: dict indexed by host name
    """

    def __init__(self, filename=None):
        """Initialize a host database.

        :param filename: if not None, initialize the database from a yaml
            file. See HostDB.load_yaml_db method for details about the expected
            format
        :type filename: str | None
        """
        self.hosts = {}

        if filename is not None:
            self.load_yaml_db(filename)

    @property
    def hostnames(self):
        """Return the current list of host names.

        :return: a list of hostnames
        :rtype: list[str]
        """
        return self.hosts.keys()

    def add_host(self, hostname, platform, version, **data):
        """Add/Update a host entry.

        :param hostname: host name
        :type hostname: str
        :param platform: platform name (see e3.platform)
        :type platform : str
        :param version: platform/OS version
        :type version: str
        :param data: additional host information
        :type data: dict
        """
        self.hosts[hostname] = Host(hostname, platform, version, **data)

    def load_yaml_db(self, filename):
        """Load a yaml configuration file.

        The yaml file should be a dictionaty indexed by host name. Each entry
        should be a dictionary containing at least the following two keys:

        * build_platform: the platform name
        * build_os_version: the platform/os version

        Additional keys for a host entry will be considered as additional data

        :param filename: path the the yaml file
        :type filename: str
        """
        with open(filename, 'rb') as fd:
            content = yaml.load(fd)

        for hostname, hostinfo in content.iteritems():
            platform = hostinfo['build_platform']
            version = hostinfo['build_os_version']
            del hostinfo['build_platform']
            del hostinfo['build_os_version']
            self.add_host(hostname, platform, version, **hostinfo)

    def __getitem__(self, key):
        return self.hosts[key]

    def get(self, key, default=None):
        """Return the Host named ``key`` of ``default``.

        :param key: host name
        :type key: str
        :param default: default value to return if not found
        :type default: None | Host
        :rtype: Host
        """
        return self.hosts.get(key, default)
