#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import os
import sys

from e3.env import Env

try:
    from ConfigParser import ConfigParser
except ImportError:  # py3-only
    from configparser import ConfigParser


def main(coverage_rc):
    os_name = Env().build.os.name
    test_dir = os.path.abspath(os.path.dirname(__file__))

    config = ConfigParser()
    base_conf, target_conf = ((
        os.path.join(test_dir, 'coverage', '%s.rc' % name)
        for name in ('base', os_name)))

    with open(coverage_rc, 'w') as dest:
        config.read(base_conf)
        config.read(target_conf)

        # exclude lines is built with: base.rc config
        exclude_lines = config.get('report', 'exclude_lines').splitlines()

        # add all <os>-only patterns
        exclude_lines += [
            '%s-only' % o
            for o in ('darwin', 'linux', 'solaris', 'windows', 'bsd', 'aix')
            if o != os_name]
        # exclude this specific os
        exclude_lines.append('%s: no cover' % os_name)

        # special case for unix
        if os_name != 'windows':
            exclude_lines.append('unix: no cover')

        if os.path.basename(sys.executable).startswith('python3'):
            exclude_lines.append('py2-only')
        else:
            exclude_lines.append('py3-only')

        config.set('report', 'exclude_lines', '\n'.join(exclude_lines))
        config.write(dest)


if __name__ == '__main__':
    main(sys.argv[1])
