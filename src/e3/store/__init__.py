from __future__ import annotations

from typing import TYPE_CHECKING

import stevedore

if TYPE_CHECKING:
    from typing import Any
    from e3.store.cache.backends.base import Cache
    from e3.store.backends.base import Store


def load_store(name: str, configuration: Any, cache: Cache) -> Store:
    plugin = stevedore.DriverManager("e3.store", name)

    return plugin.driver(configuration, cache)
