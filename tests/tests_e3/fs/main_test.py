from pathlib import Path
import os
import re
import sys
import shutil

import e3.diff
import e3.fs
import e3.hash
import e3.os.fs

from e3.os.process import Run

import pytest


def test_cp():
    current_dir = os.getcwd()
    hash_test = os.path.join(current_dir, "hash_test")
    e3.fs.cp(__file__, hash_test)
    assert e3.hash.sha1(__file__) == e3.hash.sha1(hash_test)

    a = os.path.join(current_dir, "a")
    a1 = os.path.join(a, "a1")
    b1 = os.path.join(a, "b", "b1")

    e3.fs.mkdir(a)
    e3.fs.echo_to_file(a1, "a1")
    e3.fs.mkdir(os.path.join(a, "b"))
    e3.fs.echo_to_file(b1, "b1")

    dest = os.path.join(current_dir, "dest")
    e3.fs.mkdir(dest)
    e3.fs.cp(a, dest, recursive=True)
    assert os.path.exists(os.path.join(dest, "a", "a1"))
    assert os.path.exists(os.path.join(dest, "a", "b", "b1"))

    dest2 = os.path.join(current_dir, "dest2")

    with pytest.raises(e3.fs.FSError) as err:
        e3.fs.cp("*.non_existing", dest2)
    assert "can't find files matching" in str(err.value)

    with pytest.raises(e3.fs.FSError) as err:
        e3.fs.cp([a1, b1], dest2)  # type: ignore[arg-type]
    assert "target should be a directory" in str(err.value)

    e3.fs.mkdir(dest2)
    e3.fs.cp([a1, b1], dest2)  # type: ignore[arg-type]
    assert os.path.exists(os.path.join(dest2, "a1"))
    assert os.path.exists(os.path.join(dest2, "b1"))

    dest3 = os.path.join(current_dir, "dest3")
    e3.fs.mkdir(dest3)
    e3.fs.cp(a, dest3, copy_attrs=False, recursive=True)
    e3.fs.cp(a1, dest3, copy_attrs=False)

    assert os.path.exists(os.path.join(dest3, "a", "a1"))
    assert os.path.exists(os.path.join(dest3, "a", "b", "b1"))
    assert os.path.exists(os.path.join(dest3, "a1"))

    with pytest.raises(e3.fs.FSError):
        e3.fs.cp(a, os.path.join("does", "not", "exist"))


def test_pathlib():
    """Minimal test to see whether pathlib.Path are also accepted."""
    path_a = Path("a")
    path_a.touch()
    path_b = Path("b")
    e3.fs.cp(path_a, path_b)
    assert path_b.is_file()

    assert e3.fs.directory_content(Path(".")) == ["a", "b"]
    e3.fs.echo_to_file(Path("c"), "c")
    assert e3.fs.directory_content(Path(".")) == ["a", "b", "c"]

    assert set(e3.fs.find(Path("."))) == {"./a", "./b", "./c"}

    assert e3.fs.get_filetree_state(Path(".")) == e3.fs.get_filetree_state(".")

    assert e3.fs.ls(Path("a")) == ["a"]
    assert e3.fs.ls([Path("a"), Path("c")]) == ["a", "c"]

    d = Path("d")
    e3.fs.mkdir(d)
    assert d.is_dir()
    file_in_d = d / "a_file"
    file_in_d.touch()

    assert e3.fs.splitall(file_in_d) == ("d", "a_file")

    e3.fs.mv(path_a, Path("e"))
    e3.fs.mv(d, Path("f"))
    assert [e3.os.fs.unixpath(p) for p in e3.fs.directory_content(Path("."))] == [
        "b",
        "c",
        "e",
        "f/",
        "f/a_file",
    ]

    e3.fs.sync_tree(Path("f"), Path("a"))

    e3.fs.rm(path_b)
    e3.fs.rm([Path("e"), Path("f")], recursive=True)
    assert [e3.os.fs.unixpath(p) for p in e3.fs.directory_content(Path("."))] == [
        "a/",
        "a/a_file",
        "c",
    ]


def test_mv_with_iterables():
    for idx in range(10):
        e3.os.fs.touch(f"a{idx}")

    def star(d):
        for star_idx in range(10):
            yield f"{d}{star_idx}"

    e3.fs.mkdir("dst")
    e3.fs.mv(star("a"), "dst")
    for idx in range(10):
        assert os.path.exists(os.path.join("dst", f"a{idx}"))

    def dst_star(d):
        for dst_star_idx in range(10):
            yield Path("dst") / f"{d}{dst_star_idx}"

    assert e3.fs.ls(dst_star("a")) == [
        os.path.join("dst", f"a{idx}") for idx in range(10)
    ]

    e3.fs.rm(dst_star("a"))
    for idx in range(10):
        assert not os.path.exists(os.path.join("dst", f"a{idx}"))


@pytest.mark.skipif(sys.platform == "win32", reason="test using symlink")
def test_cp_symlink():
    e3.os.fs.touch("c")
    os.symlink("c", "c_sym")
    e3.fs.cp("c_sym", "d", preserve_symlinks=True)
    assert os.path.islink("d")


def test_echo():
    dest_file = "echo_test"
    e3.fs.echo_to_file(dest_file, "foo")
    e3.fs.echo_to_file(dest_file, "foo")
    e3.fs.echo_to_file(dest_file, "bar", append=True)
    with open(dest_file) as foobar_f:
        assert foobar_f.read() == "foobar"

    e3.fs.echo_to_file(dest_file, ["line1", "line2"])
    with open(dest_file) as fd:
        assert fd.read().strip() == "line1\nline2"


def test_find():
    d = os.path.dirname(__file__)
    parent_d = os.path.dirname(d)

    result = {os.path.abspath(f) for f in e3.fs.find(parent_d)}
    assert os.path.abspath(__file__) in result
    assert os.path.abspath(d) not in result

    result = e3.fs.find(parent_d, include_dirs=True, include_files=False)
    result = {os.path.abspath(f) for f in result}
    assert os.path.abspath(d) in result
    assert os.path.abspath(__file__) not in result

    result = e3.fs.find(parent_d, include_dirs=True, include_files=True)
    result = {os.path.abspath(f) for f in result}
    assert os.path.abspath(d) in result
    assert os.path.abspath(__file__) in result

    result = e3.fs.find(parent_d, pattern="__in*py")
    assert {os.path.basename(f) for f in result} == {"__init__.py"}

    result = e3.fs.find(parent_d, pattern="fs")
    assert {os.path.basename(f) for f in result} == set()

    result = e3.fs.find(parent_d, pattern="fs", include_dirs=True)
    assert {os.path.basename(f) for f in result} == {"fs"}


def test_ls(caplog):
    e3.os.fs.touch("a")
    e3.fs.ls("a", emit_log_record=True)
    assert "ls a" in caplog.text

    e3.os.fs.touch("b")
    e3.os.fs.touch("c")

    assert e3.fs.ls("*") == ["a", "b", "c"]

    # Reproduce issue #213: add test with generator
    assert e3.fs.ls(k for k in ("a", "c")) == ["a", "c"]


def test_mkdir(caplog):
    e3.fs.mkdir("subdir")
    for record in caplog.records:
        assert "mkdir" in record.msg


def test_mkdir_exists(caplog):
    os.makedirs("subdir")
    e3.fs.mkdir("subdir")
    for record in caplog.records:
        assert "mkdir" not in record.msg


def test_mv():
    for fname in ("a1", "a2", "a3", "1", "2", "3", "11", "12", "13"):
        e3.os.fs.touch(fname)

    e3.fs.mkdir("b")

    e3.fs.mv("a*", "b")
    for fname in ("a1", "a2", "a3"):
        assert os.path.isfile(os.path.join("b", fname))

    e3.os.fs.touch("a1")
    with pytest.raises(e3.fs.FSError) as err:
        e3.fs.mv("a*", "b")
    assert re.search("Destination path 'b.*a1' already exists", str(err))

    e3.fs.mv("1", "b")
    assert os.path.isfile(os.path.join("b", "1"))

    with pytest.raises(e3.fs.FSError):
        e3.fs.mv(("1*", " 2", "3"), "c")

    e3.fs.mkdir("c")
    e3.fs.mv(("1*", "2", "3"), "c")
    for fname in ("2", "3", "11", "12", "13"):
        assert os.path.isfile(os.path.join("c", fname))

    with pytest.raises(e3.fs.FSError):
        e3.fs.mv("d*", "b")

    e3.fs.mv("b/", "B/")
    with pytest.raises(e3.fs.FSError) as err:
        e3.fs.mv("B", "B/b")
    assert "Cannot move a directory 'B' into itself 'B/b" in str(err)


def test_tree_state():
    import time

    current_dir = os.getcwd()
    d = os.path.dirname(os.path.dirname(__file__))
    state = e3.fs.get_filetree_state(d)
    assert isinstance(state, str)

    e3.fs.sync_tree(d, os.path.join(current_dir))
    state2 = e3.fs.get_filetree_state(current_dir)
    assert state != state2

    state3 = e3.fs.get_filetree_state(current_dir)
    assert state2 == state3

    # To ensure that file system resolution is not hiding
    # changes
    time.sleep(2)

    e3.os.fs.touch("toto")
    e3.os.fs.touch("toto2")
    state4 = e3.fs.get_filetree_state(current_dir)
    assert state4 != state3
    hidden = os.path.join(current_dir, ".h")
    e3.fs.mkdir(hidden)
    state5 = e3.fs.get_filetree_state(current_dir)
    assert state5 == state4
    e3.os.fs.touch(".toto")
    state6 = e3.fs.get_filetree_state(current_dir)
    assert state6 == state5

    # Make sure that ignore_hidden=False returns a different result
    state6_with_hidden = e3.fs.get_filetree_state(current_dir, ignore_hidden=False)
    assert state6_with_hidden != state6

    state6 = e3.fs.get_filetree_state("toto")
    assert isinstance(state6, str)

    with open("toto", "wb") as f:
        f.write(b"hello world.")

    # check that get_filetree_state accept unicode
    state7 = e3.fs.get_filetree_state("toto")
    assert isinstance(state7, str)
    assert state7 != state6

    # check that get_filetree_state with hash_content is different that the
    # previous state
    state8 = e3.fs.get_filetree_state("toto", hash_content=True)
    assert isinstance(state8, str)
    assert state8 != state7

    # check that get_filetree_state with hash_content is working with directory
    # and is different that the previous call without hash_content to true
    with open("toto2", "wb") as f:
        f.write(b"hello world 2.")

    state9 = e3.fs.get_filetree_state(current_dir, hash_content=True)
    assert isinstance(state9, str)
    assert state9 != state4


@pytest.mark.skipif(sys.platform == "win32", reason="test using symlink")
def test_sync_tree_with_symlinks():
    current_dir = os.getcwd()
    a = os.path.join(current_dir, "a")
    b = os.path.join(current_dir, "b")
    m1 = os.path.join(current_dir, "m1")
    m2 = os.path.join(current_dir, "m2")
    m3 = os.path.join(current_dir, "m3")

    e3.fs.mkdir(m1)
    e3.fs.mkdir(m2)
    e3.fs.mkdir(m3)

    with open(a, "w") as f:
        f.write("a")

    with open(b, "w") as f:
        f.write("b")

    e3.fs.cp(a, os.path.join(m1, "c"))
    os.symlink(b, os.path.join(m2, "c"))
    os.symlink(m2, os.path.join(m3, "c"))

    # we start with m2/c -> b
    # so m2/c and b points to the same content
    assert e3.diff.diff(b, os.path.join(m2, "c")) == ""
    assert e3.diff.diff(b, os.path.join(m1, "c"))
    e3.fs.sync_tree(m1, m2)

    # after the sync tree m1/c = m2/c
    assert e3.diff.diff(os.path.join(m1, "c"), os.path.join(m2, "c")) == ""

    # and m2/c is not a symlink anymore so does not
    # have the same content as b
    assert e3.diff.diff(b, os.path.join(m2, "c"))

    # we start with m3/c -> m2
    assert os.path.exists(os.path.join(m3, "c", "c"))
    e3.fs.sync_tree(m1, m3)
    # after the sync tree m1/c = m3/c
    assert e3.diff.diff(os.path.join(m1, "c"), os.path.join(m3, "c")) == ""

    # and m3/c is not a link to m2
    assert not os.path.exists(os.path.join(m3, "c", "c"))
    assert os.path.exists(os.path.join(m2, "c"))


@pytest.mark.skipif(sys.platform != "win32", reason="test relevant only on win32")
def test_sync_tree_case_insensitive():
    e3.fs.mkdir("test/a")
    e3.fs.mkdir("test/b")
    e3.os.fs.touch("test/a/initial.txt")
    e3.os.fs.touch("test/b/Initial.txt")
    e3.fs.mkdir("test/a/Subdir")
    e3.fs.mkdir("test/b/subdir")
    e3.fs.mkdir("test/a/Subdir2")
    e3.fs.echo_to_file("test/b/OLD.txt", "Version_Old")
    e3.fs.echo_to_file("test/a/old.txt", "Version_New")
    e3.fs.echo_to_file("test/b/old2.txt", "Version_Old")
    e3.fs.echo_to_file("test/a/OLD2.txt", "Version_New")

    e3.fs.sync_tree("test/a", "test/b")
    assert e3.fs.directory_content("test/b") == e3.fs.directory_content("test/a")

    # Adjust some casing of a file that is up-to-date. Sync_tree should be case
    # preserving and thus adjust the casing
    shutil.move("test/b/OLD2.txt", "test/b/Old2.txt")
    e3.fs.sync_tree("test/a", "test/b")
    assert e3.fs.directory_content("test/b") == e3.fs.directory_content("test/a")


def test_sync_tree_preserve_timestamps():
    """Run sync_tree without preserving timestamps."""
    e3.fs.mkdir("a")
    e3.fs.mkdir("b")
    with open("a/content", "w") as f:
        f.write("content")
    with open("a/content2", "w") as f:
        f.write("content2")
    with open("b/content", "w") as f:
        f.write("content")
    with open("b/content2", "w") as f:
        f.write("content1")
    e3.fs.sync_tree("a", "b", preserve_timestamps=False)

    with open("b/content2") as f:
        assert f.read() == "content2"


def test_sync_tree_no_delete():
    """Run sync_tree without deleting."""
    e3.fs.mkdir("a")
    e3.fs.mkdir("b")
    with open("a/content", "w") as f:
        f.write("content")
    with open("a/content2", "w") as f:
        f.write("content2")
    with open("b/content", "w") as f:
        f.write("content")
    with open("b/content2", "w") as f:
        f.write("content1")

    e3.os.fs.touch("b/todelete")
    e3.fs.sync_tree("a", "b", delete=False)
    assert os.path.exists("b/todelete")

    e3.fs.sync_tree("a", "b")
    assert not os.path.exists("b/todelete")


@pytest.mark.skipif(sys.platform == "win32", reason="test using symlink")
def test_sync_tree_links():
    """Check handling of symbolic links in sync_tree."""
    e3.fs.mkdir("a")
    e3.fs.mkdir("b")
    e3.fs.mkdir("c")
    with open("a/content", "w") as f:
        f.write("content")
    os.symlink(os.path.join(os.getcwd(), "a", "content"), "a/link")
    e3.fs.sync_tree("a", "b", preserve_timestamps=False)

    with open("b/link") as f:
        assert f.read() == "content"


@pytest.mark.skipif(sys.platform != "win32", reason="test using Windows mklink")
def test_sync_tree_dir_links() -> None:
    """Check handling of symbolic directory links in sync_tree.

    This test is Windows specific, and aims only at making sure issue
    https://github.com/AdaCore/e3-core/issues/738 is fixed.
    """
    e3.fs.mkdir("a/b")
    # Create a directory symlink with `mklink /D`, and make sure it is listed
    # as a <SYMLINKD> by the `DIR` command.
    os.chdir("a")
    mklink_process = Run(["CMD", "/C", "MKLINK /D c b"])
    os.chdir("..")

    if mklink_process.status != 0:
        pytest.skip("Insufficient permissions to create symbolic links on Windows")

    dir_process: Run = Run(["CMD", "/C", "DIR a"])
    assert "<SYMLINKD>" in dir_process.out

    # Sync trees.
    e3.fs.sync_tree("a", "d", preserve_timestamps=False)

    # Make sure the <SYMLINKD> type has been created, and not transformed
    # into a file symlink as stated by
    # https://github.com/AdaCore/e3-core/issues/738
    dir_process = Run(["CMD", "/C", "DIR d"])
    assert "<SYMLINKD>" in dir_process.out


def test_sync_tree_top_source_is_link():
    """Check handling of source top is a link."""
    e3.fs.mkdir("a")
    with open("a/content", "w") as f:
        f.write("content")

    try:
        # Symlinks are supported on Windows, but the user must have sufficient
        # permissions.
        os.symlink(
            os.path.join(os.getcwd(), "a"),
            os.path.join(os.getcwd(), "b"),
            target_is_directory=True,
        )
    except Exception as e:
        if sys.platform == "win32":
            pytest.skip("Insufficient permissions to create symbolic links on Windows")
        else:
            raise e

    # Sync tree in "c", source top is "b", which is a symlink to "a".
    e3.fs.mkdir("c")
    e3.fs.sync_tree(
        os.path.join(os.getcwd(), "b"),
        os.path.join(os.getcwd(), "c", "a"),
        preserve_timestamps=False,
    )

    # Make sure `c/a` is not a symlink
    assert not os.path.islink(os.path.join(os.getcwd(), "c", "a"))
    with open("c/a/content") as f:
        assert f.read() == "content"


def test_sync_tree_does_not_exist():
    """Check error message when sync_tree source does not exist."""
    with pytest.raises(e3.fs.FSError) as err:
        e3.fs.sync_tree("doesnotexist", "dest")
    assert "doesnotexist does not exist" in str(err)


def test_rm_on_error():
    e3.fs.mkdir("a")
    e3.fs.mkdir("a/b")
    e3.os.fs.touch("a/b/c")
    os.chmod("a/b/c", 0o000)
    os.chmod("a/b", 0o000)

    e3.fs.mkdir("a/d")
    e3.os.fs.touch("a/d/e")
    os.chmod("a/d/e", 0o000)
    os.chmod("a/d", 0o500)

    e3.fs.mkdir("a/f")
    e3.fs.mkdir("a/f/g")
    os.chmod("a/f", 0o500)

    e3.fs.rm("a", True)


def test_rm_list():
    """Call rm with list of files to remove."""
    e3.os.fs.touch("a")
    e3.os.fs.touch("b")
    e3.fs.rm(["a", "b"], glob=False)
    assert not os.path.exists("a")
    assert not os.path.exists("b")


def test_rm_symlink():
    e3.fs.mkdir("a")
    try:
        os.symlink("a", "b")
    except Exception:
        # This means symlinks are not supported on that system or not allowed
        return

    e3.fs.rm("b", recursive=True)
    assert not os.path.exists("b")
    assert os.path.exists("a")

    e3.os.fs.touch("d")
    os.symlink("d", "e")
    e3.fs.rm("e", recursive=True)
    assert not os.path.exists("e")
    assert os.path.exists("d")


def test_safe_copy():
    """sync_tree should replace directory by files and fix permissions."""
    # Check that a directory in the target dir is replaced by a file when
    # needed.
    e3.fs.mkdir("a")
    with open("a/f", "w") as f:
        f.write("file")
    e3.fs.mkdir("b")
    e3.fs.mkdir("b/f")
    e3.fs.sync_tree("a", "b")
    assert os.path.isfile("b/f")

    # Check that target file permission are changed to allow copying new
    # content.
    e3.fs.mkdir("c")
    e3.os.fs.touch("c/f")
    os.chmod("c/f", 0o000)
    e3.fs.sync_tree("a", "c")
    with open("c/f") as f:
        assert f.read() == "file"


@pytest.mark.skipif(sys.platform == "win32", reason="test using symlink")
def test_safe_copy_links():
    """sync_tree should replace directory by symlinks when needed."""
    e3.fs.mkdir("a")
    e3.fs.mkdir("a/d")
    os.symlink("f", "a/l")
    e3.fs.mkdir("b")
    e3.fs.mkdir("b/l")
    e3.fs.sync_tree("a", "b")
    assert os.path.islink("b/l")


def test_sync_tree_dir_vs_file():
    """sync_tree should replace file by directory when needed."""
    e3.fs.mkdir("a")
    e3.fs.mkdir("a/d")
    e3.fs.mkdir("b")
    e3.os.fs.touch("b/d")
    e3.fs.sync_tree("a", "b")
    assert os.path.isdir("b/d")


def test_safe_mkdir():
    """sync_tree should copy dir even when no permission in target dir."""
    e3.fs.mkdir("a")
    e3.fs.mkdir("a/a")
    e3.fs.mkdir("b")
    os.chmod("b", 0o000)
    e3.fs.sync_tree("a", "b")
    assert os.path.isdir("b/a")


def test_splitall():
    assert e3.fs.splitall("a/b") == ("a", "b")
    assert e3.fs.splitall("/a") == ("/", "a")
    assert e3.fs.splitall("/a/b") == ("/", "a", "b")
    assert e3.fs.splitall("/a/b/") == ("/", "a", "b")


def test_sync_tree_with_file_list():
    """Test sync_tree with file_list."""
    e3.fs.mkdir("a")
    for x in range(0, 10):
        e3.os.fs.touch("a/%d" % x)

    e3.fs.mkdir("b")
    e3.fs.sync_tree("a", "b", file_list=["3", "7"])
    assert os.path.exists("b/3")
    assert os.path.exists("b/7")
    assert not os.path.exists("b/5")


def test_sync_tree_with_ignore():
    """Test sync_tree with ignore."""
    e3.fs.mkdir("a")
    for x in range(0, 10):
        e3.os.fs.touch("a/%d" % x)

    e3.fs.mkdir("b")
    e3.fs.sync_tree("a", "b", ignore=["/3", "/7"])
    assert not os.path.exists("b/3")
    assert not os.path.exists("b/7")
    assert os.path.exists("b/5")

    e3.os.fs.touch("b/7")
    e3.fs.sync_tree("a", "b", ignore=["/3", "/7"])
    assert os.path.exists("b/7")
    e3.fs.sync_tree("a", "b", ignore=["/3", "/7"], delete_ignore=True)
    assert not os.path.exists("b/7")

    e3.os.fs.touch("a/test.py")
    e3.fs.sync_tree("a", "b", ignore="*.py", delete_ignore=True)
    assert not os.path.exists("b/test.py")
    for x in range(0, 10):
        assert os.path.exists("b/" + str(x))


def test_extension():
    assert e3.fs.extension("/home/file1.2.txt") == ".txt"
    assert e3.fs.extension("file2.tar.gz") == ".tar.gz"
    assert e3.fs.extension("file2.tar") == ".tar"
    assert e3.fs.extension("file2.tar.bz2") == ".tar.bz2"


def test_directory_content():
    """Test e3.fs.directory_content."""
    e3.fs.mkdir("test1")
    e3.fs.mkdir("test1/test2")
    e3.os.fs.touch(os.path.join("test1", "test1.txt"))
    e3.os.fs.touch(os.path.join("test1", "test2.txt"))
    assert e3.fs.directory_content("test1") == [
        "test1.txt",
        "test2.txt",
        "test2" + os.sep,
    ]
    assert e3.fs.directory_content("test1", unixpath=True) == [
        "test1.txt",
        "test2.txt",
        "test2/",
    ]
    assert e3.fs.directory_content("test1", include_root_dir=True, unixpath=True) == [
        "test1/test1.txt",
        "test1/test2.txt",
        "test1/test2/",
    ]
