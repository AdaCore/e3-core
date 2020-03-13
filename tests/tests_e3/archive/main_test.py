import os
import sys

import e3.archive
import e3.fs
import e3.log
import e3.os.fs

import pytest


@pytest.mark.parametrize("ext", (".tar.gz", ".tar.bz2", ".tar", ".zip"))
def test_unpack(ext):
    dir_to_pack = os.path.dirname(__file__)

    test_dir = os.path.basename(dir_to_pack)

    dest = "dest"
    e3.fs.mkdir(dest)

    archive_name = "e3-core" + ext

    try:
        e3.archive.create_archive(archive_name, os.path.abspath(dir_to_pack), dest)
        assert os.path.exists(os.path.join(dest, archive_name))

        with pytest.raises(e3.archive.ArchiveError):
            e3.archive.unpack_archive(
                os.path.join(dest, archive_name), os.path.join(dest, "dest")
            )

        e3.fs.mkdir(os.path.join(dest, "dest"))
        e3.archive.unpack_archive(
            os.path.join(dest, archive_name), os.path.join(dest, "dest")
        )

        assert os.path.exists(
            os.path.join(dest, "dest", test_dir, os.path.basename(__file__))
        )

        e3.fs.mkdir(os.path.join(dest, "dest2"))
        e3.archive.unpack_archive(
            os.path.join(dest, archive_name),
            os.path.join(dest, "dest2"),
            selected_files=(
                e3.os.fs.unixpath(os.path.join(test_dir, os.path.basename(__file__))),
            ),
            remove_root_dir=True,
        )

        assert os.path.exists(os.path.join(dest, "dest2", os.path.basename(__file__)))

        # Test wildcard if not .zip format
        # ??? not supported?
        if ext != ".zip":
            e3.fs.mkdir(os.path.join(dest, "dest3"))
            e3.archive.unpack_archive(
                os.path.join(dest, archive_name),
                os.path.join(dest, "dest3"),
                selected_files=(os.path.join(test_dir, "*.py"),),
                remove_root_dir=True,
            )

            assert os.path.exists(
                os.path.join(dest, "dest3", os.path.basename(__file__))
            )

        e3.archive.create_archive(
            "e3" + ext, os.path.abspath(dir_to_pack), dest, from_dir_rename="e3rename"
        )
        e3.fs.mkdir(os.path.join(dest, "dest4"))
        e3.archive.unpack_archive(
            os.path.join(dest, "e3" + ext), os.path.join(dest, "dest4")
        )
        assert os.path.join(dest, "dest4", "e3rename")

        # force use of sync_tree
        e3.fs.rm(os.path.join(dest, "dest4", "e3rename", os.path.basename(__file__)))
        e3.archive.unpack_archive(
            os.path.join(dest, "e3" + ext),
            os.path.join(dest, "dest4", "e3rename"),
            remove_root_dir=True,
        )
        assert os.path.exists(
            os.path.join(dest, "dest4", "e3rename", os.path.basename(__file__))
        )

    finally:
        e3.fs.rm(dest, True)


def test_unsupported():
    """Test unsupported archive format."""
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.create_archive("foo.foo", os.getcwd(), "dest")
        raise
    assert 'unknown format "foo.foo"' in str(err)


def test_unpackerror():
    """Test unpack_archive when archive file is not found."""
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.unpack_archive("foo", "dest")
    assert "cannot find foo" in str(err)


def test_unpack_cmd():
    """Test custom unpack_cmd."""
    dir_to_pack = os.path.dirname(__file__)

    dest = "dest"
    e3.fs.mkdir(dest)

    archive_name = "e3-core.tar"

    e3.archive.create_archive(archive_name, os.path.abspath(dir_to_pack), dest)

    all_dest = "all_dest"
    e3.fs.mkdir(all_dest)

    # use cp to 'extract' the archive
    e3.archive.unpack_archive(
        os.path.join(dest, archive_name), all_dest, unpack_cmd=e3.fs.cp
    )
    assert os.path.exists(os.path.join(all_dest, archive_name))

    # Use a custom unpack function and verify that it is called with
    # the expected arguments
    class TestResult(object):
        def store_result(self, **kwargs):
            self.kwargs = kwargs

    t = TestResult()

    def custom_unpack(filename, dest, selected_files):
        t.store_result(f=filename, d=dest, s=selected_files)

    e3.archive.unpack_archive(
        os.path.join(dest, archive_name),
        all_dest,
        unpack_cmd=custom_unpack,
        selected_files=["bar"],
    )
    assert os.path.basename(t.kwargs["f"]) == archive_name
    assert t.kwargs["d"] == all_dest
    assert t.kwargs["s"] == ["bar"]


def test_unpack_files():
    """Test unpack_archive with selected_files."""
    e3.fs.mkdir("d")
    e3.fs.mkdir(os.path.join("d/a"))
    e3.fs.mkdir(os.path.join("d/a/c"))
    e3.fs.mkdir(os.path.join("d/a/d"))
    e3.fs.mkdir(os.path.join("d/b"))

    dest = "dest"
    e3.fs.mkdir(dest)

    result_dir = "result"
    e3.fs.mkdir(result_dir)

    archive_name = "e3-core.tar"
    e3.archive.create_archive(archive_name, os.path.abspath(os.path.join("d")), dest)

    # No file starting with a path starting with 'a'.
    # Should raise ArchiveError
    with pytest.raises(e3.archive.ArchiveError):
        e3.archive.unpack_archive(
            os.path.join(dest, archive_name), result_dir, selected_files=["a"]
        )

    # unpacking d/a should work
    e3.archive.unpack_archive(
        os.path.join(dest, archive_name), result_dir, selected_files=["d/a"]
    )
    assert os.path.exists(os.path.join(result_dir, "d", "a", "c"))
    assert os.path.exists(os.path.join(result_dir, "d", "a", "d"))
    assert not os.path.exists(os.path.join(result_dir, "d", "b"))


def test_unpack_error():
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


def test_zip_no_root_dir():
    """Create a zip with no_root_dir."""
    e3.fs.mkdir("from")
    e3.os.fs.touch(os.path.join("from", "afile"))
    e3.fs.mkdir("dest")
    e3.archive.create_archive(
        "pkg.zip", os.path.abspath("from"), "dest", no_root_dir=True
    )
    e3.fs.mkdir("result")
    e3.archive.unpack_archive(os.path.join("dest", "pkg.zip"), "result")
    assert os.path.exists(os.path.join("result", "afile"))


def test_remove_root_dir():
    """Try create_archive no_root_dir and unpack_archive remove_root_dir."""
    e3.fs.mkdir("from")
    e3.os.fs.touch(os.path.join("from", "a"))
    e3.os.fs.touch(os.path.join("from", "b"))
    e3.fs.mkdir("dest")

    # Create an archive with two root dirs (from and dest)
    e3.archive.create_archive(
        "pkg.zip", os.path.abspath(os.getcwd()), "dest", no_root_dir=True
    )
    e3.fs.mkdir("result")

    # unpacking the archive with remote_root_dir should fail
    with pytest.raises(e3.archive.ArchiveError) as err:
        e3.archive.unpack_archive(
            os.path.join("dest", "pkg.zip"), "result", remove_root_dir=True
        )
    assert "does not have a unique root dir" in str(err)

    # In 'auto' mode, the fallback will extract the two root dirs
    e3.archive.unpack_archive(
        os.path.join("dest", "pkg.zip"), "result", remove_root_dir="auto"
    )
    assert os.path.exists(os.path.join("result", "from", "a"))
    assert os.path.exists(os.path.join("result", "dest"))

    # Running it again with use sync_tree
    e3.fs.rm(os.path.join("result", "from", "a"))
    e3.archive.unpack_archive(
        os.path.join("dest", "pkg.zip"), "result", remove_root_dir="auto"
    )
    assert os.path.exists(os.path.join("result", "from", "a"))


def test_empty():
    """Create an archive with an empty content."""
    e3.fs.mkdir("from")
    e3.fs.mkdir("dest")
    e3.fs.mkdir("result")
    e3.archive.create_archive(
        "pkg.zip", os.path.abspath("from"), "dest", no_root_dir=True
    )

    # Remove root dir should be a noop
    e3.archive.unpack_archive(
        os.path.join("dest", "pkg.zip"), "result", remove_root_dir=True
    )
    assert os.listdir("result") == []


@pytest.mark.skipif(sys.platform == "win32", reason="test executable attribute")
def test_zip_attributes():
    zip_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.zip")
    e3.fs.mkdir("result")
    e3.archive.unpack_archive(zip_file, "result", remove_root_dir=True)
    assert os.access("result/test.sh", os.X_OK)


def test_archive_with_readonly_dir():
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
        os.path.join("dest", "pkg.tar.gz"), "result", remove_root_dir=True
    )
    assert os.path.isfile(os.path.join("result", "readonly_dir", "file.txt"))
