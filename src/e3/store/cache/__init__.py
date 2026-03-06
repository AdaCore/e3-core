"""Store caching layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import stevedore

if TYPE_CHECKING:
    from typing import Any

    from e3.store.cache.backends.base import Cache


def load_cache(name: str = "file-cache", configuration: Any = None) -> Cache:
    """Load a cache backend by name.

    :param name: name of the cache backend to load
    :param configuration: configuration for the cache backend
    :return: a cache backend instance
    """
    plugin: stevedore.DriverManager = stevedore.DriverManager(
        namespace="e3.store.cache.backend", name=name
    )
    return plugin.driver(configuration)
