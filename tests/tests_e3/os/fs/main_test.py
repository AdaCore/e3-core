import numbers
import os
import stat
import sys
import tempfile
import time

import e3.fs
import e3.os.fs

import pytest


def test_cd():
    with pytest.raises(e3.os.fs.OSFSError) as err:
        e3.os.fs.cd("doesnotexist")

    assert "doesnotexist" in str(err)


@pytest.mark.xfail(
    sys.platform == "win32", reason="not completely supported on windows"
)
def test_chmod():
    os.umask(0o022)
    e3.os.fs.touch("a")

    def check_mode(filename, mode):
        fmode = stat.S_IMODE(os.stat(filename).st_mode)
        assert fmode == mode, "{} != {}".format(oct(fmode), oct(mode))

    with pytest.raises(e3.os.fs.OSFSError) as err:
        e3.os.fs.chmod("666", "a")
    assert "not supported" in str(err)

    os.chmod("a", 0o666)
    check_mode("a", 0o666)

    e3.os.fs.chmod("u-w", "a")
    check_mode("a", 0o466)

    e3.os.fs.chmod("a+wx", "a")
    check_mode("a", 0o777)

    e3.os.fs.chmod("-w", "a")
    check_mode("a", 0o577)

    e3.os.fs.chmod("o=u", "a")
    check_mode("a", 0o575)

    e3.os.fs.chmod("u=g", "a")
    check_mode("a", 0o775)

    e3.os.fs.chmod("u+", "a")
    check_mode("a", 0o775)

    e3.os.fs.chmod("g=rw", "a")
    check_mode("a", 0o765)

    e3.os.fs.chmod("a=rwx", "a")
    check_mode("a", 0o777)

    os.chmod("a", 0o666)

    e3.os.fs.chmod("u=rwx,g=rwx", "a")
    check_mode("a", 0o776)

    e3.os.fs.chmod("u=rwx,g=rwx,o=rwx", "a")
    check_mode("a", 0o777)


@pytest.mark.xfail(
    sys.platform == "win32", reason="windows specific rm not yet added to e3-core"
)
def test_rm():
    base = tempfile.mkdtemp()
    try:
        bc = os.path.join(base, "b", "c")
        os.makedirs(bc)
        e3.os.fs.touch(os.path.join(bc, "d"))
        e3.os.fs.chmod("a-w", bc)

        with pytest.raises(OSError):
            e3.os.fs.safe_remove(os.path.join(bc, "d"))

        # Use the high-level rm function to force the deletion
        e3.fs.rm(os.path.join(bc, "d"))

        assert not os.path.exists(os.path.join(bc, "d"))
        e3.os.fs.safe_rmdir(bc)
        assert not os.path.exists(bc)

    finally:
        e3.fs.rm(base, True)


def test_mv():
    os.makedirs("a")
    e3.os.fs.mv("a", "b")
    assert os.path.isdir("b")

    os.makedirs("c")
    e3.os.fs.mv("b", "c")
    assert os.path.isdir(os.path.join("c", "b"))

    e3.os.fs.touch("d")
    os.makedirs("dest")
    e3.os.fs.mv("d", "dest")

    assert os.path.isfile(os.path.join("dest", "d"))


def test_df():
    cwd = os.getcwd()
    statfs = e3.os.fs.df(cwd)
    assert isinstance(statfs, numbers.Integral)
    statfs = e3.os.fs.df(cwd, True)
    assert all(isinstance(elt, numbers.Integral) for elt in statfs)


def test_maxpath():
    maxPath = e3.os.fs.max_path()
    assert isinstance(maxPath, numbers.Integral)


def test_touch():
    e3.os.fs.touch("a")
    assert os.path.exists("a")

    now = time.time()
    os.utime("a", (now - 10000, now))

    e3.os.fs.touch("a")

    assert os.stat("a").st_atime - now < 100


def test_which():
    path_to_e3 = e3.os.fs.which("e3")
    assert os.path.isfile(path_to_e3)

    assert e3.os.fs.which(path_to_e3) == path_to_e3
