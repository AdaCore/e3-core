from __future__ import absolute_import, division, print_function
import stevedore


def load_event_manager(name, configuration):
    plugin = stevedore.DriverManager(
        'e3.event.manager',
        name)

    return plugin.driver(configuration)
