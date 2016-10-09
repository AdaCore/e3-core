from e3.anod.buildspace import BuildSpace
from e3.os.fs import touch

import os
import pytest


def test_reset():
    """Verify that BuildSpace reset() delete expected content."""
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    bs.create()
    for name in bs.dirs:
        touch(os.path.join(bs.get_subdir(name), 'a'))

    # Reset delete all dirs except log and result by default
    bs.reset()
    for name in bs.dirs:
        exists = os.path.exists(
            os.path.join(bs.get_subdir(name), 'a'))
        if name in ('log', 'results'):
            assert exists
        else:
            assert not exists


def test_subdir():
    """Check error handling of get_subdir."""
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    with pytest.raises(ValueError):
        bs.get_subdir('foo')
