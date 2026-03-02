"""Tests for e3.archive."""

import os
import sys
import tempfile
import io

import e3.archive
import e3.fs
import e3.log
import e3.os.fs

import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.mark.parametrize("ext", (".tar.gz", ".tar.bz2", ".tar.xz", ".tar", ".zip"))
def test_unpack(ext) -> None:
    dir_to_pack = os.path.dirname(__file__)

    test_dir = os.path.basename(dir_to_pack)

    dest = Path("dest")
    e3.fs.mkdir(dest)

    archive_name = "e3-core" + ext

    try:
        e3.archive.create_archive(archive_name, os.path.abspath(dir_to_pack), str(dest))
        assert (dest / archive_name).exists()

        with pytest.raises(e3.archive.ArchiveError):
            e3.archive.unpack_archive(str(dest / archive_name), str(dest / "dest"))

        e3.fs.mkdir(dest / "dest")
        e3.archive.unpack_archive(str(dest / archive_name), str(dest / "dest"))

        assert (dest / "dest" / test_dir / os.path.basename(__file__)).exists()

        e3.fs.mkdir(dest / "dest2")
        e3.archive.unpack_archive(
            str(dest / archive_name),
            str(dest / "dest2"),
            selected_files=(
                e3.os.fs.unixpath(Path(test_dir, os.path.basename(__file__))),
            ),
            remove_root_dir=True,
        )

        assert (dest / "dest2" / os.path.basename(__file__)).exists()

        # Test wildcard if not .zip format
        # ??? not supported?
        if ext != ".zip":
            e3.fs.mkdir(Path(dest, "dest3"))
            e3.archive.unpack_archive(
                str(dest / archive_name),
                str(dest / "dest3"),
                selected_files=(Path(test_dir, "*.py"),),
                remove_root_dir=True,
            )

            assert (dest / "dest3" / os.path.basename(__file__)).exists()

        e3.archive.create_archive(
            "e3" + ext,
            os.path.abspath(dir_to_pack),
            str(dest),
            from_dir_rename="e3rename",
        )
        e3.fs.mkdir(dest / "dest4")
        e3.archive.unpack_archive(str(dest / ("e3" + ext)), str(dest / "dest4"))
        assert dest / "dest4" / "e3rename"

        # force use of sync_tree
        e3.fs.rm(dest / "dest4" / "e3rename" / os.path.basename(__file__))
        e3.archive.unpack_archive(
            str(dest / ("e3" + ext)),
            str(dest / "dest4" / "e3rename"),
            remove_root_dir=True,
        )
        assert (dest / "dest4" / "e3rename" / os.path.basename(__file__)).exists()

    finally:
        e3.fs.rm(dest, True)


@pytest.mark.parametrize("ext", (".tar.gz", ".zip"))
def test_unpack_fileobj(ext) -> None:
    dir_to_pack = os.path.dirname(__file__)

    test_dir = os.path.basename(dir_to_pack)

    dest = Path("dest")
    e3.fs.mkdir(dest)

    archive_name = "e3-core" + ext

    try:
        fo = io.BytesIO()
        e3.archive.create_archive(
            filename=archive_name,
            from_dir=os.path.abspath(dir_to_pack),
            fileobj=fo,
        )

        fo.seek(0)
        e3.fs.mkdir(dest / "dest2")
        e3.archive.unpack_archive(
            filename=archive_name,
            dest=str(dest / "dest2"),
            fileobj=fo,
            selected_files=(
                e3.os.fs.unixpath(Path(test_dir, os.path.basename(__file__))),
            ),
            remove_root_dir=True,
        )

        assert (dest / "dest2" / os.path.basename(__file__)).exists()

    finally:
        e3.fs.rm(dest, True)


def test_unsupported() -> None:
    """Test unsupported archive format."""
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.create_archive("foo.foo", str(Path.cwd()), "dest")
    assert 'unknown format "foo.foo"' in str(err)


def test_unpackerror() -> None:
    """Test unpack_archive when archive file is not found."""
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.unpack_archive("foo", "dest")
    assert "cannot find foo" in str(err)


def test_unpack_cmd() -> None:
    """Test custom unpack_cmd."""
    dir_to_pack = os.path.dirname(__file__)

    dest = Path("dest")
    e3.fs.mkdir(dest)

    archive_name = "e3-core.tar"

    e3.archive.create_archive(archive_name, os.path.abspath(dir_to_pack), str(dest))

    all_dest = "all_dest"
    e3.fs.mkdir(all_dest)

    # use cp to 'extract' the archive
    e3.archive.unpack_archive(str(dest / archive_name), all_dest, unpack_cmd=e3.fs.cp)
    assert Path(all_dest, archive_name).exists()

    # Use a custom unpack function and verify that it is called with
    # the expected arguments
    class TestResult:
        def store_result(self, **kwargs) -> None:
            self.kwargs = kwargs

    t = TestResult()

    def custom_unpack(filename, dest, selected_files) -> None:
        t.store_result(f=filename, d=dest, s=selected_files)

    e3.archive.unpack_archive(
        str(dest / archive_name),
        all_dest,
        unpack_cmd=custom_unpack,
        selected_files=["bar"],
    )
    assert os.path.basename(t.kwargs["f"]) == archive_name
    assert t.kwargs["d"] == all_dest
    assert t.kwargs["s"] == ["bar"]


def test_unpack_cmd_fileobj() -> None:
    """Test custom unpack_cmd with fileobj."""
    dir_to_pack = os.path.dirname(__file__)

    dest = Path("dest")
    e3.fs.mkdir(dest)

    archive_name = "e3-core.tar"

    fo = io.BytesIO()
    e3.archive.create_archive(
        filename=archive_name,
        from_dir=os.path.abspath(dir_to_pack),
        fileobj=fo,
    )

    all_dest = "all_dest"
    e3.fs.mkdir(all_dest)

    # Use a custom unpack function and verify that it is called with
    # the expected arguments
    class TestResult:
        def store_result(self, **kwargs) -> None:
            self.kwargs = kwargs

    t = TestResult()

    def custom_unpack(filename, dest, fileobj) -> None:
        t.store_result(f=filename, d=dest, fo=fileobj)

    fo.seek(0)
    e3.archive.unpack_archive(
        filename=archive_name,
        fileobj=fo,
        dest=all_dest,
        unpack_cmd=custom_unpack,
    )
    assert t.kwargs["f"] == archive_name
    assert t.kwargs["d"] == all_dest
    assert t.kwargs["fo"] == fo


def test_unpack_files() -> None:
    """Test unpack_archive with selected_files."""
    e3.fs.mkdir("d")
    e3.fs.mkdir(Path("d/a"))
    e3.fs.mkdir(Path("d/a/c"))
    e3.fs.mkdir(Path("d/a/d"))
    e3.fs.mkdir(Path("d/b"))

    dest = Path("dest")
    e3.fs.mkdir(dest)

    result_dir = Path("result")
    e3.fs.mkdir(result_dir)

    archive_name = "e3-core.tar"
    e3.archive.create_archive(archive_name, os.path.abspath(str(Path("d"))), str(dest))

    # No file starting with a path starting with 'a'.
    # Should raise ArchiveError
    with pytest.raises(e3.archive.ArchiveError):
        e3.archive.unpack_archive(
            str(dest / archive_name), str(result_dir), selected_files=["a"]
        )

    # unpacking d/a should work
    e3.archive.unpack_archive(
        str(dest / archive_name), str(result_dir), selected_files=["d/a"]
    )
    assert (result_dir / "d" / "a" / "c").exists()
    assert (result_dir / "d" / "a" / "d").exists()
    assert not (result_dir / "d" / "b").exists()


def test_unpack_error() -> None:
    """Test unpack errors."""
    e3.fs.mkdir("dest")
    # create an invalid tgz
    e3.os.fs.touch("foo.tgz")
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.unpack_archive("foo.tgz", "dest")
    assert "unpack_archive: Cannot untar" in str(err.value)

    # create an invalid zip
    e3.os.fs.touch("foo.zip")
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.unpack_archive("foo.zip", "dest")
    assert "unpack_archive: Cannot unzip" in str(err.value)


def test_zip_no_root_dir() -> None:
    """Create a zip with no_root_dir."""
    e3.fs.mkdir("from")
    e3.os.fs.touch(Path("from", "afile"))
    e3.fs.mkdir("dest")
    e3.archive.create_archive(
        "pkg.zip", os.path.abspath("from"), "dest", no_root_dir=True
    )
    e3.fs.mkdir("result")
    e3.archive.unpack_archive(str(Path("dest", "pkg.zip")), "result")
    assert Path("result", "afile").exists()


def test_remove_root_dir() -> None:
    """Try create_archive no_root_dir and unpack_archive remove_root_dir."""
    e3.fs.mkdir("from")
    e3.os.fs.touch(Path("from", "a"))
    e3.os.fs.touch(Path("from", "b"))
    e3.fs.mkdir("dest")

    # Create an archive with two root dirs (from and dest)
    e3.archive.create_archive(
        "pkg.zip", os.path.abspath(str(Path.cwd())), "dest", no_root_dir=True
    )
    e3.fs.mkdir("result")

    # unpacking the archive with remote_root_dir should fail
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.unpack_archive(
            str(Path("dest", "pkg.zip")), "result", remove_root_dir=True
        )
    assert "does not have a unique root dir" in str(err)

    # In 'auto' mode, the fallback will extract the two root dirs
    e3.archive.unpack_archive(
        str(Path("dest", "pkg.zip")), "result", remove_root_dir="auto"
    )
    assert Path("result", "from", "a").exists()
    assert Path("result", "dest").exists()

    # Running it again with use sync_tree
    e3.fs.rm(Path("result", "from", "a"))
    e3.archive.unpack_archive(
        str(Path("dest", "pkg.zip")), "result", remove_root_dir="auto"
    )
    assert Path("result", "from", "a").exists()


@patch("tempfile.mkdtemp", wraps=tempfile.mkdtemp)
def test_tmp_dir_root(mock_mkdtemp) -> None:
    """Try to unpack an archive with remove_root_dir and a custom tmp_dir root."""
    e3.fs.mkdir("custom_tmp_dir_root")
    e3.fs.mkdir("result")
    e3.archive.unpack_archive(
        str(Path(os.path.dirname(os.path.abspath(__file__)), "test.zip")),
        "result",
        remove_root_dir=True,
        tmp_dir_root="custom_tmp_dir_root",
    )
    mock_mkdtemp.assert_called_once_with(prefix="", dir="custom_tmp_dir_root")
    assert Path("result/test.sh").exists()


def test_empty() -> None:
    """Create an archive with an empty content."""
    e3.fs.mkdir("from")
    e3.fs.mkdir("dest")
    e3.fs.mkdir("result")
    e3.archive.create_archive(
        "pkg.zip", os.path.abspath("from"), "dest", no_root_dir=True
    )

    # Remove root dir should be a noop
    e3.archive.unpack_archive(
        str(Path("dest", "pkg.zip")), "result", remove_root_dir=True
    )
    assert os.listdir("result") == []


@pytest.mark.skipif(sys.platform == "win32", reason="test executable attribute")
def test_zip_attributes() -> None:
    zip_file = Path(os.path.dirname(os.path.abspath(__file__)), "test.zip")
    e3.fs.mkdir("result")
    e3.archive.unpack_archive(str(zip_file), "result", remove_root_dir=True)
    assert os.access("result/test.sh", os.X_OK)


def test_archive_with_readonly_dir() -> None:
    """Test unpack of archive with read-only directory."""
    e3.fs.mkdir("from")
    e3.fs.mkdir("dest")
    e3.fs.mkdir("result")
    e3.fs.mkdir("from/readonly_dir")
    e3.os.fs.touch("from/readonly_dir/file.txt")
    e3.os.fs.chmod("u=rx,go=rx", "from/readonly_dir")
    e3.archive.create_archive("pkg.tar.gz", os.path.abspath("from"), "dest")
    e3.os.fs.chmod("urwx", "from/readonly_dir")
    e3.archive.unpack_archive(
        str(Path("dest", "pkg.tar.gz")), "result", remove_root_dir=True
    )
    assert os.path.isfile(Path("result", "readonly_dir", "file.txt"))
