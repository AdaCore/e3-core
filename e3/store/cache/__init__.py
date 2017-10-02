from __future__ import absolute_import, division, print_function

import stevedore


def load_cache(name='file-cache', configuration=None):
    plugin = stevedore.DriverManager(
        namespace='e3.store.cache.backend',
        name=name)
    return plugin.driver(configuration)
