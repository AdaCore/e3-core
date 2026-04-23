"""High-Level file manipulation."""

from __future__ import annotations

import fnmatch
import glob
import hashlib
import itertools
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from platform import python_version
from typing import TYPE_CHECKING, NamedTuple

from packaging.version import Version

import e3
import e3.error
import e3.log
import e3.os.fs
from e3.collection.trie import Trie

logger = e3.log.getLogger("fs")

# Windows WSL symbolic link reparse tag
WSL_SYMLINK_TAG = 0xA000001D

# Timestamp comparison tolerance (in seconds)
TIMESTAMP_TOLERANCE = 0.001

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Sequence
    from typing import Any


class FSError(e3.error.E3Error):
    """Exception raised for file system operations errors."""


def walk_tree(
    path: str | Path, *, topdown: bool = True, follow_symlinks: bool = False
) -> Generator[tuple[str, list[os.DirEntry], list[os.DirEntry]]]:
    """Copy of the Python implementation of walk that returns DirEntry.

    The main advantage of DirEntry is that on Windows it contains both the path
    and the stat information which on Windows can save a significant amount of time
    as both information are returned by the API in one call.

    See os.walk documentation
    """
    stack: list[str | tuple[str, list[os.DirEntry], list[os.DirEntry]]] = [
        os.fspath(path)
    ]
    islink, join = os.path.islink, os.path.join

    while stack:
        top = stack.pop()
        if not isinstance(top, str):
            yield top
            continue

        dirs = []
        nondirs = []
        walk_dirs = []

        # We may not have read permission for top, in which case we can't
        # get a list of the files the directory contains.
        # We suppress the exception here, rather than blow up for a
        # minor reason when (say) a thousand readable directories are still
        # left to visit.
        try:
            scandir_it = os.scandir(top)
        except OSError:
            continue

        cont = False
        with scandir_it:
            while True:
                try:
                    try:
                        entry = next(scandir_it)
                    except StopIteration:
                        break
                except OSError:
                    cont = True
                    break

                try:
                    if not follow_symlinks:
                        is_dir = entry.is_dir(follow_symlinks=False) and (
                            not hasattr(entry, "is_junction") or not entry.is_junction()
                        )
                    else:
                        is_dir = entry.is_dir()
                except OSError:
                    # If is_dir() raises an OSError, consider the entry not to
                    # be a directory, same behaviour as os.path.isdir().
                    is_dir = False

                if is_dir:
                    dirs.append(entry)
                else:
                    nondirs.append(entry)

                if not topdown and is_dir:
                    # Bottom-up: traverse into sub-directory, but exclude
                    # symlinks to directories if followlinks is False
                    if follow_symlinks:
                        walk_into = True
                    else:
                        try:
                            is_symlink = entry.is_symlink()
                        except OSError:
                            # If is_symlink() raises an OSError, consider the
                            # entry not to be a symbolic link, same behaviour
                            # as os.path.islink().
                            is_symlink = False
                        walk_into = not is_symlink

                    if walk_into:
                        walk_dirs.append(entry.path)
        if cont:
            continue

        if topdown:
            # Yield before sub-directory traversal if going top down
            yield top, dirs, nondirs
            # Traverse into sub-directories
            for dirname in reversed(dirs):
                new_path = join(top, dirname.name)
                # bpo-23605: os.path.islink() is used instead of caching
                # entry.is_symlink() result during the loop on os.scandir() because
                # the caller can replace the directory entry during the "yield"
                # above.
                if follow_symlinks or not islink(new_path):
                    stack.append(new_path)
        else:
            # Yield after sub-directory traversal if going bottom up
            stack.append((top, dirs, nondirs))
            # Traverse into sub-directories
            stack += (new_path for new_path in reversed(walk_dirs))


def cp(
    source: str | Path,
    target: str | Path,
    copy_attrs: bool = True,
    recursive: bool = False,
    preserve_symlinks: bool = False,
) -> None:
    """Copy files.

    :param source: a glob pattern
    :param target: target file or directory. If the source resolves as
        several files then target should be a directory
    :param copy_attrs: If True, also copy all the file attributes such as
        mode, timestamps, ownership, etc.
    :param recursive: If True, recursive copy. This also preserves
        attributes; if copy_attrs is False, a warning is emitted.
    :param preserve_symlinks: if True symlinks are recreated in the
        destination folder
    :raise FSError: if an error occurs
    """
    switches = ""
    if copy_attrs:
        switches += " -p"
    if recursive:
        switches += " -r"
    logger.debug("cp %s %s->%s", switches, source, target)

    if recursive and not copy_attrs:
        logger.warning("recursive copy always preserves file attributes")

    # Starting from here ensure we only use Path objects
    if isinstance(source, str):
        source = Path(source)

    if isinstance(target, str):
        target = Path(target)

    # Compute file list and number of file to copy
    file_list = ls_paths(source, emit_log_record=False)
    file_number = len(file_list)

    if file_number == 0:
        # If there is no source files raise an error
        raise FSError(origin="cp", message=f'can\'t find files matching "{source}"')
    if file_number > 1 and not target.is_dir():
        # If we have more than one file to copy then check that target is a
        # directory
        raise FSError(origin="cp", message="target should be a directory")

    for f in file_list:
        try:
            f_dest = target / f.name if target.is_dir() else target

            if recursive and f.is_dir():
                shutil.copytree(f, f_dest, symlinks=preserve_symlinks)
            elif preserve_symlinks and f.is_symlink():  # windows: no cover
                linkto = f.readlink()
                f_dest.symlink_to(linkto)
            elif copy_attrs:
                shutil.copy2(f, f_dest)
            else:
                shutil.copy(f, f_dest)
        except Exception as e:
            msg = f"error occurred while copying {f} to {f_dest}"
            logger.exception(msg)
            raise FSError(origin="cp", message=msg) from e


def directory_content(
    path: str | Path, include_root_dir: bool = False, unixpath: bool = False
) -> list[str]:
    """Return the complete directory content (recursively).

    :param path: path for the which the content should be returned
    :param include_root_dir: if True include the root directory in the paths
        returned by the function. Otherwise return relative paths
    :param unixpath: if True return unix compatible paths (calling unixpath on
        all elements returned
    :return: a list of of path. Note that directories will end with a path
        separator
    """
    result: list[str] = []
    for root, dirs, files in os.walk(path):
        result.extend(str(Path(root, f)) for f in files)
        result.extend(str(Path(root, d)) + os.sep for d in dirs)
    if not include_root_dir:
        result = [
            (
                os.path.relpath(e, path) + os.sep
                if e.endswith(os.sep)
                else os.path.relpath(e, path)
            )
            for e in result
        ]
    if unixpath:
        result = [e3.os.fs.unixpath(e) for e in result]
    result.sort()
    return result


def echo_to_file(
    filename: str | Path, content: str | list[str], append: bool = False
) -> None:
    """Output content into a file.

    This function is useful when writing few content to a file for which we
    don't want to keep a file descriptor opened . In other cases, it's more
    efficient to open a file and use the regular python I/O functions.

    :param filename: file to write into
    :param content: string to be written
    :param append: if True append to the file, otherwise overwrite.
    """
    with Path(filename).open("a+" if append else "w+") as fd:
        if append:
            fd.seek(0, 2)

        if isinstance(content, list):
            fd.writelines(line + "\n" for line in content)
        else:
            fd.write(content)


def find(
    root: str | Path,
    pattern: str | None = None,
    include_dirs: bool = False,
    include_files: bool = True,
    follow_symlinks: bool = False,
) -> list[str]:
    """Find files or directory recursively.

    :param root: directory from which the research start
    :param pattern: glob pattern that files or directories should match in
        order to be included in the final result
    :param include_dirs: if True include directories
    :param include_files: if True include regular files
    :param follow_symlinks: if True include symbolic links

    :return: a list of files
    """
    result: list[str] = []
    for rt, dirs, files in os.walk(root, followlinks=follow_symlinks):
        root = rt.replace("\\", "/")
        if include_files:
            result.extend(
                root + "/" + f
                for f in files
                if pattern is None or fnmatch.fnmatch(f, pattern)
            )
        if include_dirs:
            result.extend(
                root + "/" + d
                for d in dirs
                if pattern is None or fnmatch.fnmatch(d, pattern)
            )
    return result


def find_paths(
    root: str | Path,
    pattern: str | None = None,
    include_dirs: bool = False,
    include_files: bool = True,
    follow_symlinks: bool = False,
) -> list[Path]:
    """Find files or directory recursively.

    :param root: directory from which the research start
    :param pattern: glob pattern that files or directories should match in
        order to be included in the final result
    :param include_dirs: if True include directories
    :param include_files: if True include regular files
    :param follow_symlinks: if True include symbolic links

    :return: a list of Path objects
    """
    return [
        Path(p)
        for p in find(
            root=root,
            pattern=pattern,
            include_dirs=include_dirs,
            include_files=include_files,
            follow_symlinks=follow_symlinks,
        )
    ]


def get_filetree_state(
    path: str | Path, ignore_hidden: bool = True, hash_content: bool = False
) -> str:
    """Compute a hash on a filetree to reflect its current state.

    :param path: root path of the file tree to be checked
    :param ignore_hidden: if True (default) then files and directories
        tarting with a dot are ignored.
    :param hash_content: if True, include the content in the hash.

    :return: a hash as a string

    By default, the function will not report changes in the hash if a file is
    modified and its attributes (size, modification time and mode) are not
    changed.
    This case is quite uncommon. By ignoring it we can compute efficiently a
    hash representing the state of the file tree without having to read the
    content of all files.
    """

    def compute_state(file_path: Path | os.DirEntry) -> bytes:
        """Compute file state as bytes.

        :param file_path: path to the file
        """
        f_stat = file_path.stat(follow_symlinks=False)

        state = ":".join(
            [
                os.fspath(file_path),
                str(f_stat.st_mode),
                str(f_stat.st_size),
                str(f_stat.st_mtime),
            ]
        )
        return state.encode("utf-8")

    def get_content(file_path: Path) -> bytes:
        """Get file content as bytes.

        :param file_path: path to the file
        """
        with file_path.open("rb") as f:
            return f.read()

    # Normalize input to Path object
    path = Path(path).absolute()
    result = hashlib.sha1(usedforsecurity=False)

    if path.is_dir():
        # Note that Path now has a walk method but this was added only on 3.12 and
        # for the moment we still support older Python versions.
        for _, dirs, files in walk_tree(path):
            if ignore_hidden:
                ignore_dirs = []
                for index, dir_entry in enumerate(dirs):
                    if dir_entry.name.startswith("."):
                        ignore_dirs.append(index)
                ignore_dirs.reverse()
                for index in ignore_dirs:
                    del dirs[index]

            for dir_entry in files:
                if ignore_hidden and dir_entry.name.startswith("."):
                    continue

                result.update(compute_state(dir_entry))

                if hash_content:
                    result.update(get_content(Path(dir_entry.path)))

    else:
        result.update(compute_state(path))

        if hash_content:
            result.update(get_content(path))

    return result.hexdigest()


def ls(
    path: str | Path | Iterable[str | Path],
    emit_log_record: bool = True,
) -> list[str]:
    """List files.

    :param path: glob pattern or glob pattern list
    :param emit_log_record: if True, emit a log (debug) record

    :return: a list of filenames

    This function do not raise an error if no file matching the glob pattern
    is encountered. The only consequence is that an empty list is returned.
    """
    if isinstance(path, str):
        path_list = [path]
    elif isinstance(path, Path):
        path_list = [os.fspath(path)]
    else:
        path_list = [os.fspath(p) for p in path]

    if emit_log_record:
        logger.debug("ls %s", " ".join(path_list))

    # We cannot use here Path.glob as only path relative to a given directory
    # are supported.
    # Note also that support for Path-like parameter in glob.glob has only been
    # introduced in Python 3.13
    return sorted(
        itertools.chain.from_iterable(glob.glob(p) for p in path_list)  # noqa: PTH207
    )


def ls_paths(
    path: str | Path | Iterable[str | Path],
    emit_log_record: bool = True,
) -> list[Path]:
    """List files.

    :param path: glob pattern or glob pattern list
    :param emit_log_record: if True, emit a log (debug) record

    :return: a list of Path objects

    This function do not raise an error if no file matching the glob pattern
    is encountered. The only consequence is that an empty list is returned.
    """
    return [Path(p) for p in ls(path=path, emit_log_record=emit_log_record)]


def mkdir(path: str | Path, mode: int = 0o755, quiet: bool = False) -> None:
    """Create a directory.

    :param path: path to create. If intermediate directories do not exist
        the procedure create them
    :param mode: default is 0755
    :param quiet: whether a log record should be emitted when creating the
        directory
    :raise FSError: if an error occurs

    This function behaves quite like mkdir -p command shell. So if the
    directory already exist no error is raised.
    """
    path = Path(path)
    if path.is_dir():
        return
    if not quiet:
        logger.debug("mkdir %s (mode=%s)", path, oct(mode))
    try:
        path.mkdir(mode=mode, parents=True)
    except Exception as e:  # defensive code
        if path.is_dir():
            # Take care of cases where in parallel execution environment
            # the directory is created after the initial test on its
            # existence and the call to makedirs
            return
        logger.exception(f"can't create {path}")
        raise FSError(origin="mkdir", message=f"can't create {path}") from e


def mv(
    source: str | Path | Iterable[str] | Iterable[Path],
    target: str | Path,
) -> None:
    """Move files.

    :param source: a glob pattern, a sequence/iterator of glob patterns, a path,
        or a sequence/iterator of paths
    :param target: target file or directory. If the source resolves as
        several files then target should be a directory

    :raise FSError: if an error occurs
    """

    def move_file(src: Path, dst: Path) -> None:
        """Reimplementation of shutil.move.

        The implementation follows shutil.move from the standard library.
        The only difference is that we use e3.fs.rm function instead of
        rmtree. This ensure moving a directory with read-only files will
        work. Note that we assume that dst is always the final destination
        (expansion into dst / basename(src) is done in the parent function).

        :param src: source file or directory
        :param dst: destination file or directory
        """
        logger.debug(f"mv {src} {dst}")

        try:
            src.rename(dst)
        except OSError as err:
            if dst.exists() and src.samefile(dst):
                # If src and dst are the same file and rename failed, there
                # is nothing to do. For note this case is useful to adjust
                # casing of a file on a case insensitive filesystem.
                # The present protection is necessary as in all subsequent
                # case an attempt is made to delete the source file.
                msg = f"Casing change of '{src}' to '{dst}' failed"
                raise FSError(msg) from err

            if src.is_symlink():
                linkto = src.readlink()
                dst.symlink_to(linkto)
                src.unlink()
            elif src.is_dir():
                if dst.absolute().is_relative_to(src.absolute()):
                    msg = f"Cannot move a directory '{src}' into itself '{dst}'"
                    raise FSError(msg) from err

                if dst.is_dir():
                    if next(dst.iterdir(), None) is None:
                        # If target directory is empty remove it
                        rm(dst, recursive=True)
                    else:
                        msg = f"Cannot overwrite non-empty directory '{dst}'"
                        raise FSError(msg) from err

                elif dst.is_file():
                    msg = f"Cannot overwrite file '{dst}' with directory '{src}'"
                    raise FSError(msg) from err

                shutil.copytree(src, dst, symlinks=True)
                rm(src, recursive=True)
            else:
                if dst.is_dir():
                    msg = f"Cannot overwrite directory '{dst}' with file '{src}'"
                    raise FSError(msg) from err

                # Make sure to delete target if this is a file.
                if dst.is_file():
                    rm(dst)

                shutil.copy2(src, dst)
                rm(src)

    try:
        # Compute file list and number of file to copy
        target = Path(target)
        file_list = ls_paths(source, emit_log_record=False)
        nb_files = len(file_list)

        if nb_files == 0:
            raise FSError(  # noqa: TRY301
                origin="mv", message=f'cannot find files matching "{source}"'
            )

        if nb_files == 1 and (not target.is_dir() or file_list[0].samefile(target)):
            # In case target is not directory or target is equal to source then the
            # effective destination is target itself. This case can only occurs when
            # the number of source files is 1.
            move_file(file_list[0], target)

        elif not target.is_dir():
            # More than one file to move but the target is not a directory
            msg = "mv"
            raise FSError(msg, f"{target} should be a directory")  # noqa: TRY301

        else:
            # In all other case the target is target / basename(source)
            for f in file_list:
                move_file(f, target / f.name)

    except Exception as e:
        logger.exception("mv operation failed")
        raise FSError(origin="mv", message=str(e)) from e


def rm(
    path: str | Path | Iterable[str] | Iterable[Path],
    recursive: bool = False,
    glob: bool = True,
) -> None:
    """Remove files.

    :param path: a glob pattern, a sequence/iterator of glob patterns, a path,
        or a sequence/iterator of paths
    :param recursive: if True do a recursive deletion. Default is False
    :param glob: if True globbing pattern expansion is used

    :raise FSError: if an error occurs

    Note that the function will not raise an error is there are no file to
    delete.
    """
    # We transform the list into a set in order to remove duplicate files in
    # the list
    if glob:
        file_list = set(ls_paths(path, emit_log_record=False))
    elif isinstance(path, (str, Path)):
        file_list = {Path(path)}
    else:
        file_list = {Path(p) for p in path}

    if file_list:
        tmp = " ".join([str(p) for p in file_list])
        logger.debug(f"rm{' -r' if recursive else ''} {tmp}")

    def onerror(
        func: Callable[..., Any], error_path: str, exc_info: tuple | BaseException
    ) -> None:
        """When shutil.rmtree fail, try again to delete the file.

        :param func: function to call on error
        :param error_path: file or directory to remove
        :param exc_info: exception raised when the first delete attempt was made
        """
        del exc_info
        path = Path(error_path)

        # First check whether the file we are trying to delete exist. If not
        # the work is already done, no need to continue trying removing it.
        if not path.exists():
            return

        if func in (os.remove, os.unlink):
            # Cannot remove error_path, call chmod and redo an attempt

            # This function is only called when deleting a file inside a
            # directory to remove, it is safe to change the parent directory
            # permission since the parent directory will also be removed.
            path.parent.chmod(0o700)

            # ??? It seems that this might be needed on windows
            path.chmod(0o700)
            e3.os.fs.safe_remove(path)

        elif func == os.rmdir:
            # Cannot remove error_path, call chmod and redo an attempt
            path.chmod(0o700)

            # Also change the parent directory permission if it will also
            # be removed.
            if recursive and path not in file_list:
                # If error_path not in the list of directories to remove it
                # means that we are already in a subdirectory.
                path.parent.chmod(0o700)
            e3.os.fs.safe_rmdir(path)

        elif func in (os.listdir, os.open):
            # Cannot read the directory content, probably a permission issue
            path.chmod(0o700)

            # And continue to delete the subdir
            if Version(python_version()) >= Version("3.12"):
                shutil.rmtree(path, onexc=onerror)
            else:
                shutil.rmtree(path, onerror=onerror)

        else:
            raise FSError(origin="rm", message=f"unknown function: {func.__name__!r}")

        # If the file still exists, let the user know through a debug message.
        if path.exists():
            logger.debug(
                f"error when running {func.__name__!r} on {path}. "
                "Element could not be removed."
            )

    for f in file_list:
        try:
            # Note: shutil.rmtree requires its argument to be an actual
            # directory, not a symbolic link to a directory
            if recursive and f.is_dir() and not f.is_symlink():
                if Version(python_version()) >= Version("3.12"):
                    shutil.rmtree(f, onexc=onerror)
                else:
                    shutil.rmtree(f, onerror=onerror)
            else:
                e3.os.fs.force_remove_file(f)

        except Exception as e:  # defensive code
            msg = f"error occurred while removing {f}"
            logger.exception(msg)
            raise FSError(origin="rm", message=msg) from e


def splitall(path: str | Path) -> tuple[str, ...]:
    """Split a path into a list of path components.

    :param path: path to split
    :return: a list of path components
    """
    dirnames: list[str] = []
    while 1:
        head, tail = os.path.split(path)
        if head == path:
            # absolute paths
            # os.path.split('/') -> ('/', '')
            dirnames.append(head)
            break
        if tail == path:
            # relative paths
            # os.path.split('..') -> ('', '..')
            dirnames.append(tail)
            break
        if tail == "":
            # ending with a directory separator
            # os.path.split('a/b/c/') -> ('a/b/c', '')
            pass
        else:
            dirnames.append(tail)
        path = head
    return tuple(reversed(dirnames))


VCS_IGNORE_LIST = (
    "RCS",
    "SCCS",
    "CVS",
    "CVS.adm",
    "RCSLOG",
    ".svn",
    ".git",
    ".hg",
    ".bzr",
    ".cvsignore",
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".gitreview",
    ".mailmap",
    ".idea",
    ".python-version",
    ".gitlab-ci",
    ".gitlab-ci.yml",
    ".vscode",
    ".github",
    "comment",
)


def sync_tree(  # noqa: PLR0915
    source: str | Path,
    target: str | Path,
    ignore: str | Sequence[str] | None = None,
    file_list: list[str] | None = None,
    delete: bool = True,
    preserve_timestamps: bool = True,
    delete_ignore: bool = False,
) -> tuple[list[str], list[str]]:
    """Synchronize the files and directories between two directories.

    :param source: the directory from where the files and directories
        need to be copied
    :param target: the target directory
    :param ignore: glob pattern or list of files or directories to ignore,
        if the name starts with `/` then only the path is taken into
        account from the root of the source (or target) directory.
        If the ignore value contains a glob pattern, it is taken in account
        only if it doesn't contain a /, since for now the filtering
        is not segmented by '/'.
    :param file_list: list of files to synchronize, if empty synchronize all
        files. Note that if file in the list is a directory then the complete
        content of that directory is included. Note also that ignore list
        takes precedence other file_list.
    :param delete: if True, remove files from target if they do not exist
        in source
    :param preserve_timestamps: if True preserve original timestamps.
        If False updated files get their timestamps set to current time.
    :param delete_ignore: if True files that are explicitly ignored
        are deleted. Note delete should be set to True in that case.
    """

    class FileInfo(NamedTuple):
        path: str
        stat: os.stat_result | None
        basename: str

    class FilesInfo(NamedTuple):
        rel_path: str
        source: FileInfo
        target: FileInfo

    # Normalize casing function for path comparison. path_key function
    # return a version of the path that is in lower case for case sensitive
    # and case preserving filesystems. The return value can be used for
    # path comparisons.
    if sys.platform == "win32":

        def path_key(p: str) -> str:
            """Normalize path for case-insensitive comparison.

            :param p: path to normalize
            """
            return p.lower()

    else:

        def path_key(p: str) -> str:
            """Normalize path for case-sensitive comparison.

            :param p: path to normalize
            """
            return p

    # normalize the list of file to synchronize
    norm_file_list = None
    if file_list is not None:
        norm_file_list = [wf.replace("\\", "/").rstrip("/") for wf in file_list]

    # normalize ignore patterns
    if ignore is not None:
        ignore = [ignore] if isinstance(ignore, str) else ignore
        norm_ignore_list = [fn.replace("\\", "/") for fn in ignore]

        ignore_path_suffixes = Trie(use_suffix=True, match_delimiter="/")
        ignore_path_prefixes = Trie(match_delimiter="/")

        ignore_base_regexp_list = []
        ignore_base_regexp: re.Pattern[str] | None = None

        for pattern in norm_ignore_list:
            pk = path_key(pattern)
            if "/" not in pk:
                # This is a regexp on the basename using fnmatch.
                ignore_base_regexp_list.append(fnmatch.translate(pk))
            elif pattern.startswith("/"):
                # An absolute path
                ignore_path_prefixes.add(pk)
            else:
                # A relative path
                ignore_path_suffixes.add(pk)

        if ignore_base_regexp_list:
            ignore_base_regexp = re.compile("|".join(ignore_base_regexp_list))

    def is_in_ignore_list(p: str) -> bool:
        """Check if a file should be ignored.

        :param p: path relative to source directory (note it starts with a /)

        :return: True if in the list of file to include
        """
        if ignore is None:
            return False

        pk = path_key(p)

        return (
            ignore_path_prefixes.match(pk)
            or ignore_path_suffixes.match(pk)
            or (
                ignore_base_regexp is not None
                and bool(re.match(ignore_base_regexp, Path(pk).name))
            )
        )

    def is_in_file_list(p: str) -> bool:
        """Check if a file should be included.

        :param p: path relative to source directory (note it starts with a /)

        :return: True if in the list of file to include
        """
        if file_list is None:
            return True
        if TYPE_CHECKING:
            assert norm_file_list is not None

        pk = path_key(p)

        return any(
            f
            for f in norm_file_list
            if path_key(f) == pk[1:]
            or pk.startswith(path_key("/" + f + "/"))
            or path_key(f).startswith(pk[1:] + "/")
        )

    def isdir(fi: FileInfo) -> bool:
        """Check if a file is a directory.

        :param fi: a FileInfo namedtuple

        :return: True if fi is a directory
        """
        return fi.stat is not None and stat.S_ISDIR(fi.stat.st_mode)

    def is_native_link(fi: FileInfo) -> bool:
        """Check if a file is a native link.

        :param fi: a FileInfo namedtuple
        :return: return True if fi is a native symbolic link. The notion
            of native link is only meaningful on Windows platform for which
            some links are not well understood by the Win32 API (WSL links)
        """
        return fi.stat is not None and stat.S_ISLNK(fi.stat.st_mode)

    def islink(fi: FileInfo) -> bool:
        """Check if a file is a link.

        :param fi: a FileInfo namedtuple

        :return: True if fi is a symbolic link
        """
        return fi.stat is not None and (
            stat.S_ISLNK(fi.stat.st_mode)
            # Check for WSL links on Windows
            or (sys.platform == "win32" and fi.stat.st_reparse_tag == WSL_SYMLINK_TAG)
        )

    def isfile(fi: FileInfo) -> bool:
        """Check if a file is a regular file.

        :param fi: a FileInfo namedtuple
        :return: True if fi is a regular file
        """
        return fi.stat is not None and stat.S_ISREG(fi.stat.st_mode)

    def cmp_files(src: FileInfo, dst: FileInfo) -> bool:
        """Fast compare two files."""
        bufsize = 8 * 1024
        with Path(src.path).open("rb") as fp1, Path(dst.path).open("rb") as fp2:
            while True:
                b1 = fp1.read(bufsize)
                b2 = fp2.read(bufsize)
                if b1 != b2:
                    return False

                if len(b1) < bufsize:
                    return True

    def need_update(src: FileInfo, dst: FileInfo) -> bool:
        """Check if dst file should updated.

        :param src: the source FileInfo object
        :param dst: the target FileInfo object

        :return: True if we should update dst
        """
        # when not preserving timestamps we cannot rely on the timestamps to
        # check if a file is up-to-date. In that case do a full content
        # comparison as last check.
        if dst.stat is None:
            return True
        src_mode = stat.S_IFMT(src.stat.st_mode)  # type: ignore[union-attr]
        dst_mode = stat.S_IFMT(dst.stat.st_mode)
        src_mtime = src.stat.st_mtime  # type: ignore[union-attr]
        dst_mtime = dst.stat.st_mtime
        return (
            src_mode != dst_mode
            or (
                preserve_timestamps and abs(src_mtime - dst_mtime) > TIMESTAMP_TOLERANCE
            )
            or src.stat.st_size != dst.stat.st_size  # type: ignore[union-attr]
            or (not preserve_timestamps and isfile(src) and not cmp_files(src, dst))
            or src.basename != dst.basename
        )

    def copystat(src: FileInfo, dst: FileInfo) -> None:
        """Update attribute of dst file with src attributes.

        :param src: the source FileInfo object
        :param dst: the target FileInfo object
        """
        assert src.stat is not None
        mode = stat.S_IMODE(src.stat.st_mode)

        if islink(src):  # windows: no cover
            if hasattr(os, "lchmod"):
                getattr(os, "lchmod")(dst.path, mode)  # noqa: B009

            if hasattr(os, "lchflags") and hasattr(src.stat, "st_flags"):
                try:
                    st_flags = src.stat.st_flags  # type: ignore[attr-defined]
                    getattr(os, "lchflags")(dst.path, st_flags)  # noqa: B009
                except OSError as why:  # defensive code
                    import errno  # noqa: PLC0415  # check platform-specific error code

                    if (
                        not hasattr(errno, "EOPNOTSUPP")
                        or why.errno != errno.EOPNOTSUPP
                    ):
                        raise

                    logger.debug("lchflags: operation not supported [EOPNOTSUPP]")
        else:
            if hasattr(os, "utime"):
                if preserve_timestamps:
                    os.utime(dst.path, ns=(src.stat.st_atime_ns, src.stat.st_mtime_ns))
                else:
                    os.utime(dst.path, None)
            if hasattr(os, "chmod"):
                Path(dst.path).chmod(mode)
            if hasattr(os, "chflags") and hasattr(src.stat, "st_flags"):
                try:
                    st_flags = src.stat.st_flags  # type: ignore[attr-defined]
                    getattr(os, "chflags")(dst.path, st_flags)  # noqa: B009
                except OSError as why:  # defensive code
                    import errno  # noqa: PLC0415  # check platform-specific error code

                    if (
                        not hasattr(errno, "EOPNOTSUPP")
                        or why.errno != errno.EOPNOTSUPP
                    ):
                        raise

                    logger.debug("chflags: operation not supported [EOPNOTSUPP]")

    def safe_copy(src: FileInfo, dst: FileInfo) -> None:
        """Copy src file into dst preserving all attributes.

        :param src: the source FileInfo object
        :param dst: the target FileInfo object
        """
        if islink(src):  # windows: no cover
            linkto = e3.os.fs.readlink(src.path)
            if not is_native_link(dst) or e3.os.fs.readlink(dst.path) != linkto:
                # Checking here if the file is a native link allows us on Windows
                # to transform Cygwin links into Win32 symlinks
                if dst.stat is not None:
                    rm(dst.path, recursive=True, glob=False)

                target_is_directory = False
                if sys.platform == "win32":
                    # This is important to try guessing the right nature of the link
                    # (i.e whether it points to a directory or a file). Indeed on
                    # Windows system symbolic links to directory and files are distinct.
                    # During a call to sync_tree we are not sure in advance what will
                    # be created first: the link or the target of the link. Thus Python
                    # cannot always guess the right nature of the link (in that case
                    # Python defaults to a link to a file).
                    # In addition this function support WSL links that may be created
                    # by Cygwin when the nature of the target is not known. Python
                    # cannot read those links so in that case doing
                    # os.path.isdir(src.path) will always return False. That's why we
                    # do the check directly on the target path.
                    # limit recursion to 32 in order not to crash on link loops
                    src_linkto_path = Path(src.path).parent / linkto
                    for _ in range(32):
                        if not src_linkto_path.exists():
                            break

                        src_linkto = FileInfo(
                            str(src_linkto_path),
                            os.lstat(src_linkto_path),
                            src_linkto_path.name,
                        )

                        if not islink(src_linkto):
                            break

                        src_linkto_path = Path(
                            src_linkto.path
                        ).parent / e3.os.fs.readlink(src_linkto.path)

                    target_is_directory = src_linkto_path.is_dir()

                Path(dst.path).symlink_to(
                    linkto, target_is_directory=target_is_directory
                )
            copystat(src, dst)
        else:
            if isdir(dst):
                # dst directory will be replaced by a file having the same
                # content as 'src'
                rm(dst.path, recursive=True, glob=False)
            elif islink(dst):
                # dst symlink will be replaced by a file having the same
                # content as 'src'
                rm(dst.path, recursive=False, glob=False)

            try:
                if dst.basename != src.basename:
                    if dst.stat is not None:
                        # Case in which the destination file exists but does
                        # not have the same casing. In that case we delete the
                        # target file and redo a copy. This occurs for example
                        # on Windos with NTFS.
                        rm(dst.path, glob=False)
                    dst = FileInfo(
                        str(Path(dst.path).parent / src.basename),
                        None,
                        src.basename,
                    )

                with (
                    Path(src.path).open("rb") as fsrc,
                    Path(dst.path).open("wb") as fdst,
                ):
                    shutil.copyfileobj(fsrc, fdst)
            except OSError:
                if dst.stat is not None:
                    rm(dst.path, glob=False)
                with (
                    Path(src.path).open("rb") as fsrc,
                    Path(dst.path).open("wb") as fdst,
                ):
                    shutil.copyfileobj(fsrc, fdst)
            copystat(src, dst)

    def safe_mkdir(src: FileInfo, dst: FileInfo) -> None:
        """Create a directory modifying parent directory permissions if needed.

        :param dst: directory to create
        """
        if isfile(dst) or islink(dst):
            rm(dst.path, glob=False)

        try:
            # Final dirname with right casing
            if dst.basename != src.basename:
                dest_dir = Path(dst.path).parent / src.basename
            else:
                dest_dir = Path(dst.path)

            if isdir(dst):
                # For directories in case of non-matching casing just do a rename
                # This ensure sync_tree is efficient in case content of the directory
                # is similar between src and dst.
                if dst.basename != src.basename:
                    Path(dst.path).rename(dest_dir)
            else:
                Path(dest_dir).mkdir(parents=True)
        except OSError:
            # in case of error to change parent directory
            # permissions. The permissions will be then
            # set correctly at the end of rsync.
            e3.os.fs.chmod("a+wx", str(Path(dst.path).parent))

            if isdir(dst):
                if dst.basename != src.basename:
                    Path(dst.path).rename(dest_dir)
            else:
                Path(dest_dir).mkdir(parents=True)

    def walk(
        root_dir: str, target_root_dir: str, entry: FilesInfo | None = None
    ) -> Iterable[FilesInfo]:
        """Walk through source and target file trees.

        :param root_dir: path to source tree
        :param target_root_dir: path to target tree
        :param entry: a FilesInfo object (used internally for the recursion)

        :return: an iterator that iterate other the relevant FilesInfo object
        """
        if entry is None:
            target_stat = None
            if Path(target_root_dir).exists():
                target_stat = os.lstat(target_root_dir)

            entry = FilesInfo(
                "",
                FileInfo(root_dir, os.lstat(root_dir), ""),
                FileInfo(target_root_dir, target_stat, ""),
            )
            yield entry

        try:
            source_names = {
                path_key(p.name): p.name for p in Path(entry.source.path).iterdir()
            }
        except Exception:  # defensive code  # noqa: BLE001
            e3.log.debug("cannot get sources list", exc_info=True)
            # Don't crash in case a source directory cannot be read
            return

        target_names = {}
        if isdir(entry.target):
            try:
                target_names = {
                    path_key(p.name): p.name for p in Path(entry.target.path).iterdir()
                }
            except Exception:  # noqa: BLE001
                e3.log.debug("cannot get targets list", exc_info=True)
                target_names = {}

        all_names = set(source_names.keys()) | set(target_names.keys())

        result = []
        for name in all_names:
            rel_path = f"{entry.rel_path}/{name}"

            source_full_path = Path(entry.source.path, source_names.get(name, name))
            target_full_path = Path(entry.target.path, target_names.get(name, name))
            source_stat = None
            target_stat = None

            if name in source_names:
                source_stat = os.lstat(source_full_path)

            source_file = FileInfo(
                str(source_full_path), source_stat, source_full_path.name
            )

            if name in target_names:
                target_stat = os.lstat(target_full_path)

            target_file = FileInfo(
                str(target_full_path), target_stat, target_full_path.name
            )

            result.append(FilesInfo(rel_path, source_file, target_file))

        for el in result:
            if is_in_ignore_list(el.rel_path):
                logger.debug("ignore %s", el.rel_path)
                if delete_ignore:
                    yield FilesInfo(
                        el.rel_path,
                        FileInfo(el.source.path, None, el.source.basename),
                        el.target,
                    )
            elif is_in_file_list(el.rel_path):
                yield el
                if isdir(el.source):
                    yield from walk(root_dir, target_root_dir, el)
            else:
                yield FilesInfo(
                    el.rel_path,
                    FileInfo(el.source.path, None, el.source.basename),
                    el.target,
                )

    source_top = os.path.normpath(source).rstrip(os.path.sep)
    target_top = os.path.normpath(target).rstrip(os.path.sep)
    copystat_dir_list = []

    logger.debug(
        "sync_tree %s -> %s [delete=%s, preserve_stmp=%s]",
        source,
        target,
        delete,
        preserve_timestamps,
    )

    if not Path(source).exists():
        raise FSError(origin="sync_tree", message=f"{source} does not exist")

    # Use realpath here, or a FileNotFoundError is raised instead of an FSError
    # if source does not exist.
    if Version(python_version()) < Version("3.10"):
        # Parameter `strict` does not exist.
        source_top = os.path.realpath(source_top)
    else:
        source_top = os.path.realpath(source_top, strict=True)

    # Keep track of deleted and updated files
    deleted_list: list[str] = []
    updated_list: list[str] = []

    for wf in walk(source_top, target_top):
        if wf.source.stat is None and wf.target.stat is not None:
            # Entry that exist only in the target file tree. Check if we
            # should delete it
            if delete:
                rm(wf.target.path, recursive=True, glob=False)
                deleted_list.append(wf.target.path)
        # At this stage we have an element to synchronize in
        # the source tree.
        elif need_update(wf.source, wf.target):
            if isfile(wf.source) or islink(wf.source):
                safe_copy(wf.source, wf.target)
                updated_list.append(wf.target.path)
            elif isdir(wf.source):
                safe_mkdir(wf.source, wf.target)
                updated_list.append(wf.target.path)
                copystat_dir_list.append((wf.source, wf.target))

    # Adjust directory permissions once all files have been copied
    for d in copystat_dir_list:
        copystat(d[0], d[1])

    return updated_list, deleted_list


def extension(path: str | Path) -> str:
    """Return the extension of a given filename.

    Contrary to os.path.splitext which returns .gz, the function will return
    .tar.gz if the file is FILENAME.tar.gz.

    :param path: a path
    :return: an extension
    """
    p = Path(path)
    ext = p.suffix
    ext2 = p.with_suffix("").suffix
    if ext2 == ".tar":
        return ext2 + ext
    return ext
