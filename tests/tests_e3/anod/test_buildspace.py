from __future__ import absolute_import, division, print_function

import datetime
import os
import sys
import time

from e3.anod.buildspace import BuildSpace
from e3.anod.error import AnodError
from e3.anod.status import ReturnValue
from e3.fingerprint import Fingerprint
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

    loaded_fp = bs.load_fingerprint(kind='build')
    assert loaded_fp == fp

    # Now make sure that load_fingerprint does not fail when the bumped
    # value is corrupted
    with open(bs.fingerprint_filename('build'), 'w') as f:
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


def test_unexpected_exception_during_fingerprint_load():
    """Check that we catch all exceptions raised during fingerprint load.
    """
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    bs.create()
    fingerprint_filename = bs.fingerprint_filename(kind='build')

    # Scenario: The fingerprint file is actually not a file...

    mkdir(fingerprint_filename)
    fp = bs.load_fingerprint(kind='build')
    assert fp == Fingerprint()
    os.rmdir(fingerprint_filename)

    # Scenario: The fingerprint file is not readable (lack of permissions
    # in this case).
    #
    # Note that we do not have an easy way to remove read permission
    # to a file when on Windows, so we simply avoid that test when
    # on that platform. This test exercises the same code as in
    # the previous scenario, so this is not a big loss.

    if sys.platform != 'win32':
        ref_fp = Fingerprint()
        ref_fp.add('key1', 'val1')
        bs.save_fingerprint(kind='build', fingerprint=ref_fp)
        os.chmod(fingerprint_filename, 0)

        fp = bs.load_fingerprint(kind='build')
        assert fp == Fingerprint()
        os.chmod(fingerprint_filename, 0o600)
        os.remove(fingerprint_filename)


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


def test_reset_tmp_dir():
    """Check that the tmp_dir is reset when the build space is created.

    REQ-EC19.
    """
    bs = BuildSpace(root_dir=os.getcwd(), primitive='build')
    marker = os.path.join(bs.get_subdir(name='tmp'), 'deleteme')
    mkdir(bs.tmp_dir)
    touch(marker)
    assert os.path.exists(marker)
    bs.create()
    assert not os.path.exists(marker)
