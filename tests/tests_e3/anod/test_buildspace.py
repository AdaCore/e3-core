import os

from e3.anod.buildspace import BuildSpace
from e3.fs import mkdir, rm
from e3.os.fs import touch

import pytest


def test_reset():
    """Verify that BuildSpace reset() delete expected content."""
    bs = BuildSpace(root_dir=os.getcwd())
    bs.create()
    for name in bs.dirs:
        touch(os.path.join(bs.subdir(name), "a"))

    # Reset delete all dirs except log and result by default
    bs.reset()
    for name in bs.dirs:
        exists = os.path.exists(os.path.join(bs.subdir(name), "a"))
        if name in ("log", "results"):
            assert exists
        else:
            assert not exists


def test_subdir():
    """Check error handling of subdir."""
    bs = BuildSpace(root_dir=os.getcwd())
    with pytest.raises(ValueError):
        bs.subdir("foo")


def test_reset_tmp_dir():
    """Check that the tmp_dir is reset when the build space is created.

    REQ-EC19.
    """
    bs = BuildSpace(root_dir=os.getcwd())
    marker = os.path.join(bs.subdir(name="tmp"), "deleteme")
    mkdir(bs.tmp_dir)
    touch(marker)
    assert os.path.exists(marker)
    bs.create()
    assert not os.path.exists(marker)


def test_build_space_exists():
    """Test the BuildSpace.exists method."""
    bs_name = os.path.abspath("foo")
    bs = BuildSpace(bs_name)

    # First, verify the behavior when the buildspace directory
    # doesn't even exist.
    assert not os.path.exists(bs_name), bs_name
    assert bs.exists() is False

    # Next, create the directory, but without anything in it.
    # In particular, the marker file isn't present, so
    # is_buildspace should still return False for that directory.
    mkdir(bs_name)
    assert bs.exists() is False

    # Create the buildspace, and then verify that is_buildspace
    # then returns True.
    bs.create()
    assert bs.exists() is True

    # Verify that we also return False if one of the subdirectories
    # is missing. To do that, first verify that the subdirectory
    # we picked does exist, then delete it, before observing
    # whether BuildSpace.exists now return False or not.
    one_subdir = bs.subdir(bs.DIRS[0])
    assert os.path.isdir(one_subdir)
    rm(one_subdir, recursive=True)
    assert bs.exists() is False
