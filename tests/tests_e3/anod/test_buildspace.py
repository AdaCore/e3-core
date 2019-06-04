from __future__ import absolute_import, division, print_function

import os

from e3.anod.buildspace import BuildSpace
from e3.fs import mkdir
from e3.os.fs import touch

import pytest


def test_reset():
    """Verify that BuildSpace reset() delete expected content."""
    bs = BuildSpace(root_dir=os.getcwd())
    bs.create()
    for name in bs.dirs:
        touch(os.path.join(bs.subdir(name), 'a'))

    # Reset delete all dirs except log and result by default
    bs.reset()
    for name in bs.dirs:
        exists = os.path.exists(
            os.path.join(bs.subdir(name), 'a'))
        if name in ('log', 'results'):
            assert exists
        else:
            assert not exists


def test_subdir():
    """Check error handling of subdir."""
    bs = BuildSpace(root_dir=os.getcwd())
    with pytest.raises(ValueError):
        bs.subdir('foo')


def test_reset_tmp_dir():
    """Check that the tmp_dir is reset when the build space is created.

    REQ-EC19.
    """
    bs = BuildSpace(root_dir=os.getcwd())
    marker = os.path.join(bs.subdir(name='tmp'), 'deleteme')
    mkdir(bs.tmp_dir)
    touch(marker)
    assert os.path.exists(marker)
    bs.create()
    assert not os.path.exists(marker)
