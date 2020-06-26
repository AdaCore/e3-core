from __future__ import annotations
from typing import TYPE_CHECKING

import stevedore

if TYPE_CHECKING:
    from typing import Any
    from e3.store.cache.backends.base import Cache


def load_cache(name: str = "file-cache", configuration: Any = None) -> Cache:
    plugin = stevedore.DriverManager(namespace="e3.store.cache.backend", name=name)
    return plugin.driver(configuration)
