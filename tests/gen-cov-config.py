#!/usr/bin/env python

from e3.env import Env

import os
import sys


def main(coverage_rc):
    os_name = Env().build.os.name
    test_dir = os.path.abspath(os.path.dirname(__file__))
    with open(coverage_rc, 'w') as dest:
        for source in ((
            os.path.join(test_dir, 'coverage', '%s.rc' % name)
                for name in ('base', os_name))):
            with open(source) as s:
                dest.write(s.read())

if __name__ == '__main__':
    main(sys.argv[1])
