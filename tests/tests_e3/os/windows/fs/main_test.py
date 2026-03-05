"""Tests for e3.os.windows.fs."""

import contextlib
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from e3.fs import mkdir, rm
from e3.os.fs import touch

if sys.platform == "win32":
    from e3.os.windows.fs import NTFile
    from e3.os.windows.native_api import (
        Access,
        FileAttribute,
        LargeFileTime,
        NTException,
        Share,
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="windows specific test",
)
def test_read_attributes() -> None:
    """Test read attributes."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_read_attr_file.txt"
    touch(test_file_path)
    ntfile = NTFile(test_file_path)
    assert "test_read_attr_file.txt" in str(ntfile)

    ntfile.read_attributes()
    assert datetime.now() - ntfile.basic_info.change_time.as_datetime < timedelta(
        seconds=10
    )


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_file_info() -> None:
    """Test file info."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_read_attr_file.txt"
    touch(test_file_path)
    ntfile = NTFile(test_file_path)
    assert "test_read_attr_file.txt" in str(ntfile)

    ntfile.read_attributes()
    assert "change_time:" in str(ntfile.basic_info)


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_write_attributes() -> None:
    """Test write attributes."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_write_attr_file.txt"
    touch(test_file_path)
    ntfile = NTFile(test_file_path)
    ntfile.read_attributes()
    ntfile.open(Access.READ_ATTRS)
    ntfile.basic_info.change_time = LargeFileTime(
        datetime.now() - timedelta(seconds=3600)
    )
    assert str(time.localtime().tm_year) in str(ntfile.basic_info.change_time)
    try:
        with pytest.raises(NTException):
            ntfile.write_attributes()
    finally:
        ntfile.close()
    ntfile.basic_info.change_time = LargeFileTime(datetime.now() - timedelta(days=3))
    ntfile.write_attributes()
    assert datetime.now() - ntfile.basic_info.change_time.as_datetime > timedelta(
        seconds=3000
    )


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_uid() -> None:
    """Test uid."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_uid.txt"
    touch(test_file_path)
    ntfile = NTFile(test_file_path)
    ntfile.read_attributes()
    assert ntfile.uid > 0

    ntfile2 = NTFile(work_dir / "non_existing.txt")

    with pytest.raises(NTException):
        print(ntfile2.uid)


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_open_file_in_dir() -> None:
    """Test open file in dir."""
    work_dir = Path.cwd()

    test_dir_path = work_dir / "dir"
    mkdir(test_dir_path)
    touch(test_dir_path / "toto.txt")

    with contextlib.closing(NTFile(test_dir_path)) as ntfile:
        ntfile.open()
        with contextlib.closing(NTFile("toto.txt", parent=ntfile)) as ntfile2:
            ntfile2.open()


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_volume_path() -> None:
    """Test volume path."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_vpath.txt"
    touch(test_file_path)
    ntfile = NTFile(test_file_path)
    assert ntfile.volume_path

    ntfile = NTFile("0:/dummy")
    with pytest.raises(NTException):
        # Choose a volume name that is unlikely to exist 0:/
        print(ntfile.volume_path)


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_move_to_trash() -> None:
    """Test move to trash."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_mv_to_trash.txt"
    touch(test_file_path)
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


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_dispose() -> None:
    """Test dispose."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_dispose.txt"
    touch(test_file_path)
    ntfile = NTFile(test_file_path)
    ntfile.open(Access.READ_DATA)
    try:
        with pytest.raises(NTException):
            ntfile.dispose()
    finally:
        ntfile.close()
    ntfile.dispose()


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_rename() -> None:
    """Test rename."""
    work_dir = Path.cwd()

    test_file_path = work_dir / "test_rename.txt"
    touch(test_file_path)
    ntfile = NTFile(test_file_path)
    ntfile.open(Access.READ_DATA)
    try:
        with pytest.raises(NTException):
            ntfile.rename(str(work_dir / "test_rename2.txt"))
    finally:
        ntfile.close()
    ntfile.rename(str(work_dir / "test_rename2.txt"))


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_iterate_on_dir() -> None:
    """Test iterate on dir."""
    work_dir = Path.cwd()

    test_dir_path = work_dir / "dir"
    mkdir(test_dir_path)

    result = set()

    def fun(name, ntfile_instance):
        del ntfile_instance
        result.add(name)
        return True, False

    try:
        ntfile = NTFile(test_dir_path)
        status = ntfile.iterate_on_dir(fun, default_result=False)
        assert not result
        assert not status
    finally:
        ntfile.close()

    for n in range(40):
        touch(test_dir_path / f"{n}.txt")
    try:
        ntfile = NTFile(test_dir_path)
        status = ntfile.iterate_on_dir(fun, default_result=False)
        assert status
        assert len(result) == 40
    finally:
        ntfile.close()

    test_file = test_dir_path / "not-a-directory.txt"
    touch(test_file)
    ntfile = NTFile(test_file)
    try:
        with pytest.raises(NTException):
            status = ntfile.iterate_on_dir(fun, default_result=False)
    finally:
        ntfile.close()


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_is_dir_empty() -> None:
    """Test is dir empty."""
    work_dir = Path.cwd()

    test_dir_path = work_dir / "dir"
    deleted_file_path = test_dir_path / "deleted2.txt"
    deleted_file2_path = test_dir_path / "deleted.txt"
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


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_unlink() -> None:
    """Test unlink."""
    work_dir = Path.cwd()

    test_dir_path = work_dir / "dir"
    deleted_file_path = test_dir_path / "deleted2.txt"
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

        assert "READONLY" in str(ntfile2.basic_info.file_attributes)
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

    ntfile = NTFile("nul")
    with pytest.raises(NTException) as err:
        ntfile.unlink()
    ntfile.close()
    assert "NTFile.read_attributes_internal:" in str(err.value)

    # A directory that is not empty cannot be deleted
    dir_to_delete = test_dir_path / "dir_to_delete"
    mkdir(dir_to_delete)
    touch(dir_to_delete / "afile.txt")
    ntfile = NTFile(dir_to_delete)
    try:
        with pytest.raises(NTException) as err:
            ntfile.unlink()
    finally:
        ntfile.close()

    # A directory that is already opened and not empty cannot be
    # moved to trash
    dir_to_delete = test_dir_path / "dir_to_delete"
    mkdir(dir_to_delete)
    touch(dir_to_delete / "afile.txt")

    ntfile = NTFile(dir_to_delete)
    ntfile2 = NTFile(dir_to_delete)
    try:
        ntfile.open(Access.LIST_DIRECTORY, Share.ALL)
        with pytest.raises(NTException) as err:
            ntfile2.unlink()
    finally:
        ntfile.close()
        ntfile2.close()

    # Try to delete a file that we cannot open
    ntfile = NTFile(deleted_file_path)
    ntfile2 = NTFile(deleted_file_path)
    try:
        touch(deleted_file_path)
        ntfile.open(Access.READ_DATA, Share.NOTHING)
        with pytest.raises(NTException) as err:
            ntfile2.unlink()
    finally:
        ntfile.close()
        ntfile2.close()
