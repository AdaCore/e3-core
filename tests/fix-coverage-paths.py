#!/usr/bin/env python
# strip .tox/*/lib/python*/site-packages paths from coverage data
# show only paths corresponding to the real source files
# From https://github.com/danilobellini/pytest-doctest-custom/

from __future__ import absolute_import, division, print_function

import os
import sys

from coverage.data import CoverageData, PathAliases


def fix_paths(site_pkg_dir, cov_data_file):
    site_pkg_dir = os.path.abspath(site_pkg_dir)

    paths = PathAliases()
    paths.add(site_pkg_dir, '.')

    old_coverage_data = CoverageData()
    old_coverage_data.read_file(cov_data_file)

    new_coverage_data = CoverageData()
    new_coverage_data.update(old_coverage_data, paths)

    new_coverage_data.write_file(cov_data_file)


if __name__ == '__main__':
    fix_paths(sys.argv[1], sys.argv[2])
