import os
import tempfile

import pytest

import e3.fs
import e3.os.fs


def test_rm():
    base = tempfile.mkdtemp()
    try:
        bc = os.path.join(base, 'b', 'c')
        os.makedirs(bc)
        e3.os.fs.touch(os.path.join(bc, 'd'))
        e3.os.fs.chmod('a-w', bc)

        with pytest.raises(OSError):
            e3.os.fs.safe_remove(os.path.join(bc, 'd'))

        # Use the high-level rm function to force the deletion
        e3.fs.rm(os.path.join(bc, 'd'))

        assert not os.path.exists(os.path.join(bc, 'd'))
        e3.os.fs.safe_rmdir(bc)
        assert not os.path.exists(bc)

    finally:
        e3.fs.rm(base, True)


def test_mkdir(caplog):
    base = tempfile.mkdtemp()
    try:
        subdir = os.path.join(base, 'subdir')
        e3.fs.mkdir(subdir)
        for record in caplog.records():
            assert 'mkdir' in record.msg

    finally:
        e3.fs.rm(base, True)


def test_mkdir_exists(caplog):
    base = tempfile.mkdtemp()
    try:
        subdir = os.path.join(base, 'subdir')
        os.makedirs(subdir)
        for record in caplog.records():
            assert 'mkdir' not in record.msg

    finally:
        e3.fs.rm(base, True)
