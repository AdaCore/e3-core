from __future__ import absolute_import, division, print_function

import os
import sys
import tempfile

import e3.fs
import e3.os.fs
import pytest
import mock
import numbers


@pytest.mark.xfail(sys.platform == 'win32',
                   reason='windows specific rm not yet added to e3-core')
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
        for record in caplog.records:
            assert 'mkdir' in record.msg

    finally:
        e3.fs.rm(base, True)


def test_mkdir_exists(caplog):
    base = tempfile.mkdtemp()
    try:
        subdir = os.path.join(base, 'subdir')
        os.makedirs(subdir)
        for record in caplog.records:
            assert 'mkdir' not in record.msg

    finally:
        e3.fs.rm(base, True)


def test_df():
    cwd = os.getcwd()
    statfs = e3.os.fs.df(cwd)
    assert isinstance(statfs, numbers.Integral)
    statfs = e3.os.fs.df(cwd, True)
    assert all(isinstance(elt, numbers.Integral) for elt in statfs)


@pytest.mark.xfail(sys.platform == 'win32',
                   reason='windows doesnt support os.link')
def test_ln():
    e3.os.fs.touch("toto")
    with mock.patch("os.link") as mock_link, mock.patch("shutil.copy2") as mock_copy2:
        e3.os.fs.ln("toto", "tata")
        assert any([mock_link.called, mock_copy2.called])
    e3.os.fs.touch("tata")
    os.chmod("tata", 0000)
    try:
        e3.os.fs.ln("toto", "tata")
        assert False
    except Exception:
        assert True


def test_maxpath():
    maxPath = e3.os.fs.max_path()
    assert isinstance(maxPath, numbers.Integral)

