"""Low-level file manipulation.

All function here should be platform independent, should not involve globbing or
logging (unless in case of unexpected failure).
"""

from __future__ import annotations

import collections
import itertools
import os
import re
import shutil
import stat
import sys


from pathlib import Path
from typing import TYPE_CHECKING, overload

import e3.error
import e3.log

if TYPE_CHECKING:
    from typing import Any, Literal
    from collections.abc import Callable

CYGPATH_MATCH: re.Pattern[str] = re.compile(
    "/((cygdrive/|mnt/)?(?P<drive>[a-zA-Z])/)?(?P<path>.*)", re.IGNORECASE
)


class OSFSError(e3.error.E3Error):
    pass


logger = e3.log.getLogger("os_fs")


def cd(path: str | Path) -> None:
    """Change current directory.

    :param path: directory name
    :raise OSFSError: in case of error
    """
    try:
        os.chdir(path)
    except Exception as e:
        logger.error(e, exc_info=True)
        raise OSFSError(origin="cd", message=f"can't chdir to {path}\n") from e


def chmod(mode: str, filename: str | Path) -> int:
    """Chmod with interface similar to Unix tool.

    :param mode: should conform with posix specification for
        chmod utility (ex: +wx). See chmod man page for more information
    :param filename: the target file
    :return: the mode that has been set
    """
    # Developer note: for local variable names in this function
    # we try to use the words used in the opengroup specification
    # this way we can map easily between the implementation and
    # what is defined in the standard.

    whos = {"u": stat.S_IRWXU, "g": stat.S_IRWXG, "o": stat.S_IRWXO}
    perms = {"r": stat.S_IROTH, "w": stat.S_IWOTH, "x": stat.S_IXOTH}

    current_mode = os.stat(filename).st_mode

    # Retrieve umask
    umask = os.umask(0)
    os.umask(umask)

    clauses = mode.split(",")

    for clause in clauses:
        match = re.search(r"([ugoa]+)([-\+=].*)", clause)
        if match is not None:
            wholist = match.group(1)
            actionlist = match.group(2)
        else:
            wholist = ""
            actionlist = clause

        actions = re.findall(r"(?:([-\+=])?([ugo]|[0-7]+|[rwx]*))", actionlist)
        assert "".join(list(itertools.chain.from_iterable(actions))) == actionlist

        for op, permlist in actions:
            if permlist == "" and op != "=":
                continue
            else:
                if permlist in ("u", "g", "o"):
                    action_mask = current_mode & whos[permlist]
                    if permlist == "u":
                        action_mask >>= 6
                    elif permlist == "g":
                        action_mask >>= 3
                elif permlist.isdigit():
                    raise OSFSError(
                        origin="chmod",
                        message="numeric mode not supported, use os.chmod instead",
                    )
                else:
                    action_mask = 0
                    for perm in permlist:
                        action_mask |= perms[perm]

                if wholist == "":
                    action_mask = action_mask | action_mask << 3 | action_mask << 6
                    action_mask &= ~umask
                    apply_mask = stat.S_IRWXO | stat.S_IRWXU | stat.S_IRWXG
                else:
                    if "a" in wholist:
                        action_mask = action_mask | action_mask << 3 | action_mask << 6
                        apply_mask = stat.S_IRWXO | stat.S_IRWXU | stat.S_IRWXG
                    else:
                        final_action_mask = 0
                        apply_mask = 0
                        for who in wholist:
                            if who == "u":
                                final_action_mask |= action_mask << 6
                                apply_mask |= stat.S_IRWXU
                            elif who == "g":
                                final_action_mask |= action_mask << 3
                                apply_mask |= stat.S_IRWXG
                            else:
                                final_action_mask |= action_mask
                                apply_mask |= stat.S_IRWXO

                        action_mask = final_action_mask
                if op == "-":
                    current_mode &= ~action_mask
                elif op == "=":
                    current_mode = (current_mode & ~apply_mask) | action_mask
                else:
                    current_mode = current_mode | action_mask

    os.chmod(filename, current_mode)
    return current_mode


@overload
def df(path: str | Path) -> int: ...


@overload
def df(path: str | Path, full: Literal[True]) -> tuple: ...


def df(path: str | Path, full: bool = False) -> int | tuple:
    """Disk space available on the filesystem containing the given path.

    :param path: a path
    :param full: if True return full disk information otherwise only
        space left.

    :return: either space left in Mo or a py:meth:`collections.namedtuple`
        with ``total``, ``used`` and ``free`` attributes. Each attribute is
        an int representing Mo.
    """
    _ntuple_diskusage = collections.namedtuple("_ntuple_diskusage", "total used free")
    if sys.platform == "win32":  # unix: no cover
        import ctypes

        c_path = ctypes.c_wchar_p(str(path))
        GetDiskFreeSpaceEx: Callable = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
        )
        GetDiskFreeSpaceEx = GetDiskFreeSpaceEx(
            ("GetDiskFreeSpaceExW", ctypes.windll.kernel32),
            ((1, "path"), (2, "freeuserspace"), (2, "totalspace"), (2, "freespace")),
        )

        def GetDiskFreeSpaceEx_errcheck(result, func, args):  # type: ignore[no-untyped-def]
            del func
            if not result:  # defensive code
                raise ctypes.WinError()
            return args[1].value, args[2].value, args[3].value

        GetDiskFreeSpaceEx.errcheck = GetDiskFreeSpaceEx_errcheck  # type: ignore[attr-defined]
        _, total, free = GetDiskFreeSpaceEx(c_path)
        used = total - free
    else:  # windows: no cover
        # f_frsize = fundamental filesystem block size
        # f_bsize = preferred file system block size
        # The use of f_frsize seems to give more accurate results.
        st = os.statvfs(path)
        free = st.f_bavail * st.f_frsize
        total = st.f_blocks * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
    if full:
        return _ntuple_diskusage(
            total // (1024 * 1024), used // (1024 * 1024), free // (1024 * 1024)
        )
    return free // (1024 * 1024)


def __safe_unlink_func() -> (
    tuple[Callable[[str | Path], None], Callable[[str | Path], None]]
):
    """Provide a safe unlink function on windows.

    Note that all this is done to ensure that rm is working fine on Windows 7
    and 2008R2. Indeed very often, deletion will fail with access denied
    error. The typical scenario is when you spawn an executable and try to
    delete it just afterward.
    """
    if sys.platform == "win32":  # unix: no cover
        from e3.os.windows.fs import NTFile

        def win_rm(x: str | Path) -> None:
            return NTFile(x).unlink()

        return win_rm, win_rm
    else:  # windows: no cover

        def os_remove(x: str | Path) -> None:
            return os.remove(x)

        def os_rmdir(x: str | Path) -> None:
            return os.rmdir(x)

        return os_remove, os_rmdir


safe_remove, safe_rmdir = __safe_unlink_func()


def force_remove_file(path: str | Path) -> None:
    """Force file removing, changing permissions if first attempt failed.

    :param path: path of the file to remove
    """
    try:
        safe_remove(path)
    except OSError:
        # The permission of the parent directory does not allow us to remove
        # the file, temporary get write permission in the directory
        dir_path = os.path.dirname(path)
        orig_mode = os.stat(dir_path).st_mode
        chmod("u+w", dir_path)

        # ??? It seems that this might be needed on windows
        os.chmod(path, 0o700)
        safe_remove(path)
        os.chmod(dir_path, orig_mode)


def ldd_output_to_posix(ldd_output: str) -> str:
    """Transform an ``ldd`` output to POSIX paths only.

    This method does not have any impact when the ``ldd`` output has
    been executed on a Unix host, because paths are already POSIX there.

    It applies only to ``ldd`` outputs on Windows, where the paths starting
    with `/c/`, `/mnt/c/` or `/cygdrive/c/` are modified to `C:/`.

    For instance, ``/c/WINDOWS/System32/ntdll.dll`` is transformed to
    ``C:/WINDOWS/System32/ntdll.dll``.

    .. note:: The transformation is made on strings only to minimize the
        call the ``cygpath``. If a file path is found, all its occurrences
        are replaced by its POSIX value.

    :param ldd_output: The output of an ``ldd`` call to transform to contain
        only POSIX paths.

    :return: An ``ldd`` output with POSIX paths only.
    """
    posix_content: str = ldd_output

    if sys.platform == "win32":
        transformed: dict[str, str] = {}
        posix_path: str
        file_path: str | None = None
        lines: list[str] = posix_content.splitlines()
        drive: str = Path.cwd().drive.rstrip(":")

        for line in lines:
            if line.strip().endswith(":"):
                # Found an executable/dll path with linked dlls.
                file_path = line.strip()[:-1]
            elif " => " in line:
                # Here is the list of linked dlls.
                file_path = line.split(" => ", 1)[1].strip()

            # Do not run on already transformed paths.
            if file_path and file_path not in transformed:
                match = CYGPATH_MATCH.match(file_path)
                if match:
                    # If there is no drive, replace it with current drive.
                    posix_path = (
                        f"{match.group('drive') or drive}:/{match.group('path')}"
                    )

                    if posix_path != file_path:
                        # Transform all occurrences in the ldd output.
                        posix_content = posix_content.replace(file_path, posix_path)
                        transformed[file_path] = posix_path

    return posix_content


def max_path() -> int:
    """Return the maximum length for a path.

    :return: the maximum length
    """
    if sys.platform == "win32":  # unix: no cover
        from ctypes.wintypes import MAX_PATH

        return MAX_PATH
    else:  # windows: no cover
        return os.pathconf("/", "PC_PATH_MAX")


def mv(source: str | Path, target: str | Path) -> None:
    """Move a file.

    :param target: file to move
    :param source: target file or directory
    """
    # Compute file list and number of file to copy
    if os.path.isdir(source) and os.path.isdir(target):
        shutil.move(source, os.path.join(target, os.path.basename(source)))
    else:
        shutil.move(source, target)


def readlink(filename: str | Path) -> str:
    """Get target path of a symlink.

    Equivalent of os.readlink with support for WSL Windows links.

    :param filename: path containing a symlink
    :return: target of the symlink
    """
    try:
        return os.readlink(filename)
    except Exception:
        if sys.platform == "win32":
            # This might be a WSL link
            from e3.os.windows.fs import NTFile

            reparsed_link: str | None = NTFile(filename).wsl_reparse_link_target()
            if reparsed_link is not None:
                return reparsed_link
            raise
        else:
            raise


def touch(filename: str | Path) -> None:
    """Update file access and modification times. Create the file if needed.

    :param filename: file to update
    """
    if os.path.exists(filename):
        os.utime(filename, None)
    else:
        with open(filename, "w+"):
            pass


def unixpath(path: str | Path) -> str:
    r"""Convert path to Unix/Cygwin format.

    :param path: path string to convert
    :return: the converted path

    On Unix systems this function is identity. On Win32 systems it removes
    drive letter information and replace \\ by /.
    """
    if path and sys.platform == "win32":  # unix: no cover
        # Cygpath is not available so just replace \ by / and remove drive
        # information. This should work in most cases
        result = os.fspath(path).replace("\\", "/")
        m = re.match("[a-zA-Z]:(.*)", result)
        if m is not None:
            result = m.group(1)
        return result
    else:  # windows: no cover
        return os.fspath(path)


def which(prog: str | Path, paths: str | None = None, default: Any = "") -> Any:
    """Locate executable.

    :param prog: program to find
    :param paths: if not None then we use this value instead of PATH to look
        for the executable.
    :param default: default value to return if not found

    :return: absolute path to the program on success, found by searching for an
      executable in the directories listed in the environment variable PATH
      or default value if not found
    """

    def is_exe(file_path: str) -> bool:
        return os.path.isfile(file_path) and os.access(file_path, os.X_OK)

    def possible_names(file_path: str) -> list[str]:
        names = [file_path]
        if sys.platform == "win32":  # unix: no cover
            names.extend(
                [
                    file_path + ext
                    for ext in os.environ.get("PATHEXT", ".EXE").split(";")
                ]
            )
        return names

    fpath, _ = os.path.split(prog)
    if fpath:
        # Full path given, check if executable
        for progname in possible_names(os.fspath(prog)):
            if is_exe(progname):
                return progname
    else:
        # Check for all directories listed in $PATH
        if paths is None:
            paths = os.environ["PATH"]

        for pathdir in paths.split(os.pathsep):
            exe_file = os.path.join(pathdir, prog)
            for progname in possible_names(exe_file):
                if is_exe(progname):
                    return progname

    # Not found.
    return default
