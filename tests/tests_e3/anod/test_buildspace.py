from __future__ import absolute_import, division, print_function

import datetime
import os

import pytest
from e3.anod.buildspace import BuildSpace
from e3.anod.fingerprint import Fingerprint
from e3.anod.status import ReturnValue
from e3.os.fs import touch


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


def test_fingerprint():
    """Check dump/restore of fingerprint."""
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    bs.create()
    fp = Fingerprint()
    fp.add('foo', 'bar')
    bs.save_fingerprint(kind='build', fingerprint=fp)

    # Check that the fingerprint stored on disk is equal to fp
    fp_checksum = bs.load_fingerprint(kind='build', sha1_only=True)
    assert isinstance(fp_checksum, str)

    loaded_fp = bs.load_fingerprint(kind='build')
    assert loaded_fp == fp

    # Now make sure that load_fingerprint does not fail when the bumped
    # value is corrupted
    with open(os.path.join(bs.meta_dir, 'build_fingerprint.yaml'), 'w') as f:
        f.write('[')

    assert bs.load_fingerprint(kind='build') == Fingerprint()


def test_status():
    """Check dump/restore of status."""
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    bs.create()
    bs.save_last_status(kind='test', status=ReturnValue.notready)

    last_status, timestamp = bs.get_last_status(kind='test')
    assert last_status == ReturnValue.notready
    assert timestamp is not None
    assert (datetime.datetime.now() - timestamp).total_seconds() < 5
    last_status, timestamp = bs.get_last_status(kind='install')
    assert last_status == ReturnValue.missing
    assert timestamp is None


def test_logs():
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    bs.create()
    bs.set_logging()
    bs.end()
    assert os.path.isfile(bs.log_file)
    with open(bs.log_file) as f:
        assert 'anod primitive: build' in f.read()
