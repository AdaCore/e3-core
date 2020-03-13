#!/usr/bin/env python
# strip .tox/*/lib/python*/site-packages paths from coverage data
# show only paths corresponding to the real source files
# From https://github.com/danilobellini/pytest-doctest-custom/


import os
import sys

from coverage.sqldata import CoverageData
from coverage.files import PathAliases
from tempfile import NamedTemporaryFile


def fix_paths(site_pkg_dir, cov_data_file):
    site_pkg_dir = os.path.abspath(site_pkg_dir)

    paths = PathAliases()
    paths.add(site_pkg_dir, "src")

    old_cov_file = NamedTemporaryFile()
    old_cov_file.close()
    os.rename(cov_data_file, old_cov_file.name)

    old_coverage_data = CoverageData(old_cov_file.name)
    old_coverage_data.read()
    new_coverage_data = CoverageData(cov_data_file)
    new_coverage_data.update(old_coverage_data, aliases=paths)
    new_coverage_data.write()


if __name__ == "__main__":
    fix_paths(sys.argv[1], sys.argv[2])
