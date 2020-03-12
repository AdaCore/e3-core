import abc
import stevedore
from collections import namedtuple

import e3.decorator
import e3.log


class PlatformDBPlugin(object, metaclass=abc.ABCMeta):
    """Plugin API to extend the platform knowledge base.

    To create a plugin, override this class and the method ``update_db``. In
    ``update_db`` modify the values of self.cpu_info, self.os_info,
    self.platform_info, self.build_targets, and self.host_guess.

    Then add an entry points in your package in the group e3.platform_db and
    reference your new class. e.g.::

        entry_points={
            'e3.platform_db': [
                'my_db = e3.mypackage.platform_db:MyPlatformDBPlugin']}
    """

    def __init__(self, cpu_info, os_info, platform_info, build_targets, host_guess):
        self.cpu_info = cpu_info
        self.os_info = os_info
        self.platform_info = platform_info
        self.build_targets = build_targets
        self.host_guess = host_guess

    @abc.abstractmethod
    def update_db(self):
        pass  # all: no cover


class AmberCPUSupport(PlatformDBPlugin):
    """Plugin example adding support for Amber CPUs."""

    def update_db(self):
        """Add support for Amber CPUs."""
        self.cpu_info.update(
            {
                "amber23": {"endian": "little", "bits": 32},
                "amber25": {"endian": "little", "bits": 32},
            }
        )


@e3.decorator.memoize
def get_knowledge_base():
    """Load the knowledge base, including all content from plugins.

    :rtype collections.namedtuple
    :return: The knowledge base with the keys (cpu_info, os_info,
        platform_info, build_targets, host_guess)
    """
    from e3.platform_db.knowledge_base import (
        CPU_INFO,
        OS_INFO,
        PLATFORM_INFO,
        BUILD_TARGETS,
        HOST_GUESS,
    )

    e3.log.debug("loading knownledge base")
    # Load all platform_db plugins
    ext = stevedore.ExtensionManager(
        namespace="e3.platform_db",
        invoke_on_load=True,
        invoke_args=(CPU_INFO, OS_INFO, PLATFORM_INFO, BUILD_TARGETS, HOST_GUESS),
    )

    plugin_names = ext.names()

    if plugin_names:
        # Some plugins have been found
        e3.log.debug("loading knowledge base plugins %s", ",".join(plugin_names))

        ext.map_method("update_db")
    return namedtuple(
        "KnowledgeBase",
        ("cpu_info", "os_info", "platform_info", "build_targets", "host_guess"),
    )(CPU_INFO, OS_INFO, PLATFORM_INFO, BUILD_TARGETS, HOST_GUESS)
