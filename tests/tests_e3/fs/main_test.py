import os
import sys
import shutil

import e3.diff
import e3.fs
import e3.hash
import e3.os.fs

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
        e3.fs.cp([a1, b1], dest2)
    assert "target should be a directory" in str(err.value)

    e3.fs.mkdir(dest2)
    e3.fs.cp([a1, b1], dest2)
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


@pytest.mark.skipif(sys.platform == "win32", reason="test using symlink")
def test_cp_symplink():
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

    # To ensure that file system resolution is not hidding
    # changes
    time.sleep(2)

    e3.os.fs.touch("toto")
    state4 = e3.fs.get_filetree_state(current_dir)
    assert state4 != state3
    hidden = os.path.join(current_dir, ".h")
    e3.fs.mkdir(hidden)
    state5 = e3.fs.get_filetree_state(current_dir)
    assert state5 == state4
    e3.os.fs.touch(".toto")
    state6 = e3.fs.get_filetree_state(current_dir)
    assert state6 == state5
    state6 = e3.fs.get_filetree_state("toto")
    assert isinstance(state6, str)

    # check that get_filetree_state accept unicode
    state7 = e3.fs.get_filetree_state("toto")
    assert isinstance(state7, str)


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


@pytest.mark.skipif(sys.platform == "win32", reason="test using symlink")
def test_sync_tree_links():
    """Check handling of symbolink links in sync_tree."""
    e3.fs.mkdir("a")
    e3.fs.mkdir("b")
    e3.fs.mkdir("c")
    with open("a/content", "w") as f:
        f.write("content")
    os.symlink(os.path.join(os.getcwd(), "a", "content"), "a/link")
    e3.fs.sync_tree("a", "b", preserve_timestamps=False)

    with open("b/link") as f:
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


@pytest.mark.skipif(sys.platform == "win32", reason="test using symlink")
def test_rm_symlink_to_dir():
    e3.fs.mkdir("a")
    os.symlink("a", "b")
    e3.fs.rm("b", recursive=True)
    assert not os.path.exists("b")


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
