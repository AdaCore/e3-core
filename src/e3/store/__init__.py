"""Interface for downloading and caching resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

import stevedore

if TYPE_CHECKING:
    from typing import Any

    from e3.store.backends.base import Store
    from e3.store.cache.backends.base import Cache


def load_store(name: str, configuration: Any, cache: Cache) -> Store:
    """Load a store backend by name.

    :param name: name of the store backend to load
    :param configuration: configuration for the store backend
    :param cache: cache backend to use with the store
    :return: a store backend instance
    """
    plugin: stevedore.DriverManager = stevedore.DriverManager("e3.store", name)

    return plugin.driver(configuration, cache)
