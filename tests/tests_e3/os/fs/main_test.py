"""Tests for e3.os.fs."""

import numbers
import os
import stat
import sys
import tempfile
import time
from pathlib import Path

import pytest

import e3.fs
import e3.os.fs
import e3.os.process


def test_cd() -> None:
    with pytest.raises(e3.os.fs.OSFSError) as err:
        e3.os.fs.cd("doesnotexist")

    assert "doesnotexist" in str(err)


@pytest.mark.xfail(
    sys.platform == "win32", reason="not completely supported on windows"
)
def test_chmod() -> None:
    os.umask(0o022)
    e3.os.fs.touch("a")

    def check_mode(filename, mode) -> None:
        fmode = stat.S_IMODE(os.stat(filename).st_mode)
        assert fmode == mode, f"{oct(fmode)} != {oct(mode)}"

    with pytest.raises(e3.os.fs.OSFSError) as err:
        e3.os.fs.chmod("666", "a")
    assert "not supported" in str(err)

    Path("a").chmod(0o666)
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

    Path("a").chmod(0o666)

    e3.os.fs.chmod("u=rwx,g=rwx", "a")
    check_mode("a", 0o776)

    e3.os.fs.chmod("u=rwx,g=rwx,o=rwx", "a")
    check_mode("a", 0o777)


@pytest.mark.xfail(
    sys.platform == "win32", reason="windows specific rm not yet added to e3-core"
)
def test_rm() -> None:
    base = tempfile.mkdtemp()
    try:
        bc = Path(base, "b", "c")
        os.makedirs(bc)
        e3.os.fs.touch(bc / "d")
        e3.os.fs.chmod("a-w", bc)

        with pytest.raises(OSError):
            e3.os.fs.safe_remove(bc / "d")

        # Use the high-level rm function to force the deletion
        e3.fs.rm(bc / "d")

        assert not (bc / "d").exists()
        e3.os.fs.safe_rmdir(bc)
        assert not bc.exists()

    finally:
        e3.fs.rm(base, True)


def test_mv() -> None:
    os.makedirs("a")
    e3.os.fs.mv("a", "b")
    assert Path("b").is_dir()

    os.makedirs("c")
    e3.os.fs.mv("b", "c")
    assert Path("c", "b").is_dir()

    e3.os.fs.touch("d")
    os.makedirs("dest")
    e3.os.fs.mv("d", "dest")

    assert Path("dest", "d").is_file()


def test_df() -> None:
    cwd = str(Path.cwd())
    statfs = e3.os.fs.df(cwd)
    assert isinstance(statfs, numbers.Integral)
    statfs = e3.os.fs.df(cwd, True)
    assert all(isinstance(elt, numbers.Integral) for elt in statfs)


def test_anod_ldd_output_to_posix(ldd) -> None:  # type: ignore[no-untyped-def]
    # Get the ldd output of the current executable.
    ldd_output = e3.os.process.Run(["ldd", sys.executable]).out or ""
    e3.os.fs.ldd_output_to_posix(ldd_output)
    # Give several files to ldd so that the file names are also covered by the
    # test (not only the dll files)
    ldd_output = (
        e3.os.process.Run(["ldd", sys.executable, e3.os.fs.which("ldd")]).out or ""
    )
    e3.os.fs.ldd_output_to_posix(ldd_output)


def test_maxpath() -> None:
    maxPath = e3.os.fs.max_path()
    assert isinstance(maxPath, numbers.Integral)


def test_touch() -> None:
    e3.os.fs.touch("a")
    assert Path("a").exists()

    now = time.time()
    os.utime("a", (now - 10000, now))

    e3.os.fs.touch("a")

    assert os.stat("a").st_atime - now < 100


def test_which() -> None:
    path_to_e3 = e3.os.fs.which("e3")
    assert Path(path_to_e3).is_file()

    assert e3.os.fs.which(Path(path_to_e3)) == path_to_e3
