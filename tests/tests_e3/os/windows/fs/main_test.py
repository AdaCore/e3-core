from e3.os.fs import touch
from e3.fs import mkdir
from e3.os.windows.fs import NTFile
from e3.os.windows.native_api import (Access, FileTime, NTException,
                                      Share, FileAttribute)
from e3.fs import rm
from tempfile import mkdtemp
from datetime import datetime, timedelta
import os
import pytest
import sys


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_read_attributes():
    work_dir = mkdtemp()

    test_file_path = os.path.join(work_dir, 'test_read_attr_file.txt')
    touch(test_file_path)
    try:
        ntfile = NTFile(test_file_path)
        ntfile.read_attributes()
        assert datetime.now() - \
            ntfile.basic_info.creation_time.as_datetime < \
            timedelta(seconds=10)
    finally:
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_write_attributes():
    work_dir = mkdtemp()

    test_file_path = os.path.join(work_dir, 'test_write_attr_file.txt')
    touch(test_file_path)
    try:
        ntfile = NTFile(test_file_path)
        ntfile.read_attributes()
        ntfile.open(Access.READ_ATTRS)
        ntfile.basic_info.change_time = FileTime(datetime.now() -
                                                 timedelta(seconds=3600))
        try:
            with pytest.raises(NTException):
                ntfile.write_attributes()
        finally:
            ntfile.close()
        ntfile.basic_info.change_time = FileTime(datetime.now() -
                                                 timedelta(days=3))
        ntfile.write_attributes()
        assert datetime.now() - \
            ntfile.basic_info.change_time.as_datetime > \
            timedelta(seconds=3000)
    finally:
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_uid():
    work_dir = mkdtemp()

    test_file_path = os.path.join(work_dir, 'test_uid.txt')
    touch(test_file_path)
    try:
        ntfile = NTFile(test_file_path)
        ntfile.read_attributes()
        assert ntfile.uid > 0

        ntfile2 = NTFile(os.path.join(work_dir, 'non_existing.txt'))

        with pytest.raises(NTException):
            ntfile2.uid

    finally:
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_open_file_in_dir():
    work_dir = mkdtemp()

    test_dir_path = os.path.join(work_dir, 'dir')
    mkdir(test_dir_path)
    touch(os.path.join(test_dir_path, 'toto.txt'))
    try:
        ntfile = NTFile(test_dir_path)
        ntfile.open()
        ntfile2 = NTFile('toto.txt', parent=ntfile)
        ntfile2.open()
    finally:
        ntfile.close()
        ntfile2.close()
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_volume_path():
    work_dir = mkdtemp()

    test_file_path = os.path.join(work_dir, 'test_vpath.txt')
    touch(test_file_path)
    try:
        ntfile = NTFile(test_file_path)
        assert ntfile.volume_path

        with pytest.raises(NTException):
            ntfile = NTFile('Y:/dummy')
            ntfile.volume_path
    finally:
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_move_to_trash():
    work_dir = mkdtemp()

    test_file_path = os.path.join(work_dir, 'test_mv_to_trash.txt')
    touch(test_file_path)
    try:
        ntfile = NTFile(test_file_path)
        ntfile.open(Access.READ_DATA)
        try:
            with pytest.raises(NTException):
                ntfile.move_to_trash()
        finally:
            ntfile.close()
        trash_path = ntfile.trash_path
        ntfile.move_to_trash()
        rm(trash_path)

    finally:
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_dispose():
    work_dir = mkdtemp()

    test_file_path = os.path.join(work_dir, 'test_dispose.txt')
    touch(test_file_path)
    try:
        ntfile = NTFile(test_file_path)
        ntfile.open(Access.READ_DATA)
        try:
            with pytest.raises(NTException):
                ntfile.dispose()
        finally:
            ntfile.close()
        ntfile.dispose()

    finally:
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_rename():
    work_dir = mkdtemp()

    test_file_path = os.path.join(work_dir, 'test_rename.txt')
    touch(test_file_path)
    try:
        ntfile = NTFile(test_file_path)
        ntfile.open(Access.READ_DATA)
        try:
            with pytest.raises(NTException):
                ntfile.rename(os.path.join(work_dir, 'test_rename2.txt'))
        finally:
            ntfile.close()
        ntfile.rename(os.path.join(work_dir, 'test_rename2.txt'))

    finally:
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_iterate_on_dir():
    work_dir = mkdtemp()

    test_dir_path = os.path.join(work_dir, 'dir')
    mkdir(test_dir_path)

    result = set()

    def fun(name, ntfile_instance):
        result.add(name)
        return True, False

    for n in range(0, 40):
        touch(os.path.join(test_dir_path, '%s.txt' % n))
    try:
        ntfile = NTFile(test_dir_path)
        status = ntfile.iterate_on_dir(fun, default_result=False)
        assert status
        assert len(result) == 40
    finally:
        ntfile.close()
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_is_dir_empty():
    work_dir = mkdtemp()

    test_dir_path = os.path.join(work_dir, 'dir')
    deleted_file_path = os.path.join(test_dir_path, 'deleted2.txt')
    deleted_file2_path = os.path.join(test_dir_path, 'deleted.txt')
    mkdir(test_dir_path)

    ntfile = NTFile(test_dir_path)
    ntfile2 = NTFile(deleted_file_path)

    try:

        assert ntfile.is_dir_empty
        touch(deleted_file_path)
        touch(deleted_file2_path)
        assert not ntfile.is_dir_empty
        ntfile2.open(Access.DELETE, Share.DELETE)
        ntfile2.dispose()
        assert not ntfile.is_dir_empty
        rm(deleted_file2_path)
        assert ntfile.is_dir_empty

    finally:
        ntfile.close()
        ntfile2.close()
        rm(work_dir, recursive=True)


@pytest.mark.skipif(sys.platform != 'win32', reason="windows specific test")
def test_unlink():
    work_dir = mkdtemp()

    test_dir_path = os.path.join(work_dir, 'dir')
    deleted_file_path = os.path.join(test_dir_path, 'deleted2.txt')
    mkdir(test_dir_path)

    ntfile = NTFile(test_dir_path)
    ntfile3 = NTFile(test_dir_path)
    ntfile2 = NTFile(deleted_file_path)

    try:
        # delete inexisting file
        ntfile2.unlink()

        # delete file with readonly attribute
        touch(deleted_file_path)
        ntfile2.read_attributes()
        ntfile2.basic_info.file_attributes.attr |= FileAttribute.READONLY
        ntfile2.write_attributes()
        ntfile2.unlink()

        # delete file already pending deletion
        touch(deleted_file_path)
        ntfile2.open(Access.DELETE, Share.DELETE)
        ntfile2.dispose()
        ntfile2.unlink()

        # delete containing directory
        ntfile.unlink()

        ntfile.close()
        ntfile2.close()

        mkdir(test_dir_path)
        ntfile.open(Access.LIST_DIRECTORY, Share.ALL)
        ntfile3.unlink()

    finally:
        ntfile.close()
        ntfile2.close()
        ntfile2.close()
        rm(work_dir, recursive=True)
