from __future__ import absolute_import, division, print_function

import datetime
import os
import time

from e3.anod.buildspace import BuildSpace
from e3.anod.error import AnodError
from e3.anod.fingerprint import Fingerprint
from e3.anod.status import ReturnValue
from e3.fs import mkdir
from e3.os.fs import touch

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

    # Try updating the fingerprint
    fp.add('key', 'value')
    bs.update_status(
        kind='build', status=ReturnValue.notready,
        fingerprint=fp)
    assert bs.get_last_status(kind='build')[0] == ReturnValue.notready
    loaded_fp = bs.load_fingerprint(kind='build')
    assert loaded_fp == fp

    # Updating build fingerprint also update install fingerprint
    loaded_fp = bs.load_fingerprint(kind='install')
    assert loaded_fp == fp

    # Now update install status

    bs.update_status(kind='install', status=ReturnValue.success)
    assert bs.get_last_status(kind='install')[0] == ReturnValue.success

    # build status should not be modified
    assert bs.get_last_status(kind='build')[0] == ReturnValue.notready


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


def test_live_logs():
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    bs.create()
    bs.set_logging(stdout_logs=True)
    bs.log_stream.write('here')
    bs.log_stream.flush()
    bs.log_stream.write('there')
    time.sleep(0.2)  # let enough time to cover the tail_thread code
    bs.end()
    with open(bs.log_file) as f:
        assert 'here' in f.read()


def test_dump_traceback():
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    bs.create()
    try:
        raise ValueError('dumping traceback now')
    except ValueError:
        with pytest.raises(AnodError) as anod_err:
            bs.dump_traceback('foo', 'test')

    assert 'dumping traceback now' in str(anod_err)

    trace_file = os.path.join(bs.log_dir, 'traceback_test')
    assert os.path.exists(trace_file)
    with open(trace_file) as f:
        assert 'dumping traceback now' in f.read()
