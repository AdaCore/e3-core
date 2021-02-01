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
from collections import namedtuple
from typing import TYPE_CHECKING

import e3
import e3.error
import e3.log
import e3.os.fs
from e3.collection.trie import Trie

logger = e3.log.getLogger("fs")

if TYPE_CHECKING:
    from typing import Callable, Iterable, List, Optional, Sequence, Tuple


class FSError(e3.error.E3Error):
    pass


def cp(
    source: str,
    target: str,
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

    # Compute file list and number of file to copy
    file_list = ls(source, emit_log_record=False)
    file_number = len(file_list)

    if file_number == 0:
        # If there is no source files raise an error
        raise FSError(origin="cp", message=f'can\'t find files matching "{source}"')
    elif file_number > 1:
        # If we have more than one file to copy then check that target is a
        # directory
        if not os.path.isdir(target):
            raise FSError(origin="cp", message="target should be a directory")

    for f in file_list:
        try:
            if os.path.isdir(target):
                f_dest = os.path.join(target, os.path.basename(f))
            else:
                f_dest = target

            if recursive and os.path.isdir(f):
                shutil.copytree(f, f_dest, symlinks=preserve_symlinks)
            elif preserve_symlinks and os.path.islink(f):  # windows: no cover
                linkto = os.readlink(f)
                os.symlink(linkto, f_dest)
            elif copy_attrs:
                shutil.copy2(f, f_dest)
            else:
                shutil.copy(f, f_dest)
        except Exception as e:
            logger.error(e, exc_info=True)
            raise FSError(
                origin="cp", message=f"error occurred while copying {f}"
            ).with_traceback(sys.exc_info()[2])


def directory_content(
    path: str, include_root_dir: bool = False, unixpath: bool = False
) -> List[str]:
    """Return the complete directory content (recusrsively).

    :param path: path for the which the content should be returned
    :param include_root_dir: if True include the root directory in the paths
        returned by the function. Otherwise return relative paths
    :param unixpath: if True return unix compatible paths (calling unixpath on
        all elements returned
    :return: a list of of path. Note that directories will end with a path
        separator
    """
    result = []
    for root, dirs, files in os.walk(path):
        for f in files:
            result.append(os.path.join(root, f))
        for d in dirs:
            result.append(os.path.join(root, d) + os.sep)
    if not include_root_dir:
        result = [
            os.path.relpath(e, path) + os.sep
            if e.endswith(os.sep)
            else os.path.relpath(e, path)
            for e in result
        ]
    if unixpath:
        result = [e3.os.fs.unixpath(e) for e in result]
    result.sort()
    return result


def echo_to_file(filename: str, content: str | List[str], append: bool = False) -> None:
    """Output content into a file.

    This function is useful when writing few content to a file for which we
    don't want to keep a file descriptor opened . In other cases, it's more
    efficient to open a file and use the regular python I/O functions.

    :param filename: file to write into
    :param content: string to be written
    :param append: if True append to the file, otherwise overwrite.
    """
    with open(filename, "a+" if append else "w+") as fd:
        if append:
            fd.seek(0, 2)

        if isinstance(content, list):
            for line in content:
                fd.write(line + "\n")
        else:
            fd.write(content)


def find(
    root: str,
    pattern: Optional[str] = None,
    include_dirs: bool = False,
    include_files: bool = True,
    follow_symlinks: bool = False,
) -> List[str]:
    """Find files or directory recursively.

    :param root: directory from which the research start
    :param pattern: glob pattern that files or directories should match in
        order to be included in the final result
    :param include_dirs: if True include directories
    :param include_files: if True include regular files
    :param follow_symlinks: if True include symbolic links

    :return: a list of files
    """
    result = []
    for root, dirs, files in os.walk(root, followlinks=follow_symlinks):
        root = root.replace("\\", "/")
        if include_files:
            for f in files:
                if pattern is None or fnmatch.fnmatch(f, pattern):
                    result.append(root + "/" + f)
        if include_dirs:
            for d in dirs:
                if pattern is None or fnmatch.fnmatch(d, pattern):
                    result.append(root + "/" + d)
    return result


def get_filetree_state(path: str, ignore_hidden: bool = True) -> str:
    """Compute a hash on a filetree to reflect its current state.

    :param path: root path of the file tree to be checked
    :param ignore_hidden: if True (default) then files and directories
        tarting with a dot are ignored.
    :return: a hash as a string

    The function will not report changes in the hash if a file is modified
    and its attributes (size, modification time and mode) are not changed.
    This case is quite uncommon. By ignoring it we can compute efficiently a
    hash representing the state of the file tree without having to read the
    content of all files.
    """

    def compute_state(file_path: str) -> bytes:
        f_stat = os.lstat(file_path)

        state = ":".join(
            [file_path, str(f_stat.st_mode), str(f_stat.st_size), str(f_stat.st_mtime)]
        )
        return state.encode("utf-8")

    path = os.path.abspath(path)
    result = hashlib.sha1()
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            if ignore_hidden:
                ignore_dirs = []
                for index, name in enumerate(dirs):
                    if name.startswith("."):
                        ignore_dirs.append(index)
                ignore_dirs.reverse()
                for index in ignore_dirs:
                    del dirs[index]

            for path in files:
                if ignore_hidden and path.startswith("."):
                    continue

                full_path = os.path.join(root, path)
                result.update(compute_state(full_path))

    else:
        result.update(compute_state(path))
    return result.hexdigest()


def ls(path: str | List[str], emit_log_record: bool = True) -> List[str]:
    """List files.

    :param path: glob pattern or glob pattern list
    :param emit_log_record: if True, emit a log (debug) record

    :return: a list of filenames

    This function do not raise an error if no file matching the glob pattern
    is encountered. The only consequence is that an empty list is returned.
    """
    if isinstance(path, str):
        path_list = [path]
    else:
        path_list = list(path)

    if emit_log_record:
        logger.debug("ls %s", " ".join(path_list))

    return sorted(itertools.chain.from_iterable(glob.glob(p) for p in path_list))


def mkdir(path: str, mode: int = 0o755, quiet: bool = False) -> None:
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
    if os.path.isdir(path):
        return
    else:
        if not quiet:
            logger.debug("mkdir %s (mode=%s)", path, oct(mode))
        try:
            os.makedirs(path, mode)
        except Exception as e:  # defensive code
            if os.path.isdir(path):
                # Take care of cases where in parallel execution environment
                # the directory is created after the initial test on its
                # existence and the call to makedirs
                return
            logger.error(e)
            raise FSError(
                origin="mkdir", message=f"can't create {path}"
            ).with_traceback(sys.exc_info()[2])


def mv(source: str | List[str], target: str) -> None:
    """Move files.

    :param source: a glob pattern
    :param target: target file or directory. If the source resolves as
        several files then target should be a directory

    :raise FSError: if an error occurs
    """

    def move_file(src: str, dst: str) -> None:
        """Reimplementation of shutil.move.

        The implementation follows shutil.move from the standard library.
        The only difference is that we use e3.fs.rm function instead of
        rmtree. This ensure moving a directory with read-only files will
        work.
        """

        def same_file(src: str, dst: str) -> bool:
            if hasattr(os.path, "samefile"):
                try:
                    return os.path.samefile(src, dst)
                except OSError:
                    return False
            return os.path.normcase(os.path.abspath(src)) == os.path.normcase(
                os.path.abspath(dst)
            )

        def basename(path: str) -> str:
            sep = os.path.sep + (os.path.altsep or "")
            return os.path.basename(path.rstrip(sep))

        def destinsrc(src: str, dst: str) -> bool:
            src = os.path.abspath(src)
            dst = os.path.abspath(dst)
            if not src.endswith(os.path.sep):
                src += os.path.sep
            if not dst.endswith(os.path.sep):
                dst += os.path.sep
            return dst.startswith(src)

        real_dst = dst
        if os.path.isdir(dst):
            if same_file(src, dst):
                # We might be on a case insensitive filesystem,
                # perform the rename anyway.
                os.rename(src, dst)
                return

            real_dst = os.path.join(dst, basename(src))
            if os.path.exists(real_dst):
                raise FSError(f"Destination path '{real_dst}' already exists")
        try:
            os.rename(src, real_dst)
        except OSError:
            if os.path.islink(src):
                linkto = os.readlink(src)
                os.symlink(linkto, real_dst)
                os.unlink(src)
            elif os.path.isdir(src):
                if destinsrc(src, dst):
                    raise FSError(
                        "Cannot move a directory '%s' into itself '%s'." % (src, dst)
                    )
                shutil.copytree(src, real_dst, symlinks=True)
                rm(src, recursive=True)
            else:
                shutil.copy2(src, real_dst)
                rm(src)
        return

    if isinstance(source, str):
        logger.debug("mv %s %s", source, target)
    else:
        logger.debug("mv %s %s", " ".join(source), target)

    try:
        # Compute file list and number of file to copy
        file_list = ls(source, emit_log_record=False)
        nb_files = len(file_list)

        if nb_files == 0:
            raise FSError(origin="mv", message=f'cannot find files matching "{source}"')
        elif nb_files == 1:
            source = file_list[0]
            if os.path.isdir(source) and os.path.isdir(target):
                move_file(source, os.path.join(target, os.path.basename(source)))
            else:
                move_file(source, target)
        elif not os.path.isdir(target):
            # More than one file to move but the target is not a directory
            raise FSError("mv", f"{target} should be a directory")
        else:
            for f in file_list:
                f_dest = os.path.join(target, os.path.basename(f))
                e3.log.debug("mv %s %s", f, f_dest)
                move_file(f, f_dest)
    except Exception as e:
        logger.error(e)
        raise FSError(origin="mv", message=str(e)).with_traceback(sys.exc_info()[2])


def rm(path: str | List[str], recursive: bool = False, glob: bool = True) -> None:
    """Remove files.

    :param path: a glob pattern, or a list of glob patterns
    :param recursive: if True do a recursive deletion. Default is False
    :param glob: if True globbing pattern expansion is used

    :raise FSError: if an error occurs

    Note that the function will not raise an error is there are no file to
    delete.
    """
    if recursive:
        logger.debug("rm -r %s", str(path))
    else:
        logger.debug("rm %s", str(path))

    # We transform the list into a set in order to remove duplicate files in
    # the list
    if glob:
        file_list = set(ls(path, emit_log_record=False))
    else:
        if isinstance(path, str):
            file_list = {path}
        else:
            file_list = set(path)

    def onerror(func: Callable, error_path: str, exc_info: Tuple) -> None:
        """When shutil.rmtree fail, try again to delete the file.

        :param func: function to call on error
        :param error_path: file or directory to remove
        :param exc_info: exception raised when the first delete attempt was
             made
        """
        del exc_info
        e3.log.debug("error when running %s on %s", func, error_path)

        # First check whether the file we are trying to delete exist. If not
        # the work is already done, no need to continue trying removing it.
        if not os.path.exists(error_path):
            return

        if func in (os.remove, os.unlink):
            # Cannot remove error_path, call chmod and redo an attempt

            # This function is only called when deleting a file inside a
            # directory to remove, it is safe to change the parent directory
            # permission since the parent directory will also be removed.
            os.chmod(os.path.dirname(error_path), 0o700)

            # ??? It seems that this might be needed on windows
            os.chmod(error_path, 0o700)
            e3.os.fs.safe_remove(error_path)

        elif func == os.rmdir:
            # Cannot remove error_path, call chmod and redo an attempt
            os.chmod(error_path, 0o700)

            # Also change the parent directory permission if it will also
            # be removed.
            if recursive and error_path not in file_list:
                # If error_path not in the list of directories to remove it
                # means that we are already in a subdirectory.
                os.chmod(os.path.dirname(error_path), 0o700)
            e3.os.fs.safe_rmdir(error_path)

        elif func in (os.listdir, os.open):
            # Cannot read the directory content, probably a permission issue
            os.chmod(error_path, 0o700)

            # And continue to delete the subdir
            shutil.rmtree(error_path, onerror=onerror)

    for f in file_list:
        try:
            # When calling rmtree or remove, ensure that the string that is
            # passed to this function is unicode on Windows. Otherwise,
            # the non-Unicode API will be used and so we won't be
            # able to remove these files. On Unix don't do that as
            # we got some strange unicode "ascii codec" errors
            # (need some further investigation at some point)
            if sys.platform == "win32":  # unix: no cover
                f = str(f)

            # Note: shutil.rmtree requires its argument to be an actual
            # directory, not a symbolic link to a directory
            if recursive and os.path.isdir(f) and not os.path.islink(f):
                shutil.rmtree(f, onerror=onerror)
            else:
                e3.os.fs.force_remove_file(f)

        except Exception as e:  # defensive code
            logger.error(e)
            raise FSError(
                origin="rm", message=f"error occurred while removing {f}"
            ).with_traceback(sys.exc_info()[2])


def splitall(path: str) -> Tuple[str, ...]:
    """Split a path into a list of path components.

    :param path: path to split
    :return: a list of path components
    """
    dirnames = []  # type: List[str]
    while 1:
        head, tail = os.path.split(path)
        if head == path:
            # absolute paths
            # os.path.split('/') -> ('/', '')
            dirnames.append(head)
            break
        elif tail == path:
            # relative paths
            # os.path.split('..') -> ('', '..')
            dirnames.append(tail)
            break
        elif tail == "":
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
)


def sync_tree(
    source: str,
    target: str,
    ignore: Optional[str | Sequence[str]] = None,
    file_list: Optional[List[str]] = None,
    delete: bool = True,
    preserve_timestamps: bool = True,
    delete_ignore: bool = False,
) -> Tuple[List[str], List[str]]:
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
    :param delete_ignore: if True files that are explicitely ignored
        are deleted. Note delete should be set to True in that case.
    """
    # Some structure used when walking the trees to be synched
    FilesInfo = namedtuple("FilesInfo", ["rel_path", "source", "target"])

    # The basename in the FileInfo structure is used to compare casing of
    # source and destination.
    FileInfo = namedtuple("FileInfo", ["path", "stat", "basename"])

    # Normalize casing function for path comparison. path_key function
    # return a version of the path that is in lower case for case sensitive
    # and case preserving filesystems. The return value can be used for
    # path comparisons.
    if sys.platform == "win32":

        def path_key(p: str) -> str:
            return p.lower()

    else:

        def path_key(p: str) -> str:
            return p

    # normalize the list of file to synchronize
    norm_file_list = None
    if file_list is not None:
        norm_file_list = [wf.replace("\\", "/").rstrip("/") for wf in file_list]

    # normalize ignore patterns
    if ignore is not None:
        norm_ignore_list = [fn.replace("\\", "/") for fn in ignore]

        ignore_path_suffixes = Trie(use_suffix=True, match_delimiter="/")
        ignore_path_prefixes = Trie(match_delimiter="/")

        ignore_base_regexp_list = []
        ignore_base_regexp: Optional[re.Pattern[str]] = None

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
                and bool(re.match(ignore_base_regexp, os.path.basename(pk)))
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

    def islink(fi: FileInfo) -> bool:
        """Check if a file is a link.

        :param fi: a FileInfo namedtuple

        :return: True if fi is a symbolic link
        """
        return fi.stat is not None and stat.S_ISLNK(fi.stat.st_mode)

    def isfile(fi: FileInfo) -> bool:
        """Check if a file is a regular file.

        :param fi: a FileInfo namedtuple
        :return: True if fi is a regular file
        """
        return fi.stat is not None and stat.S_ISREG(fi.stat.st_mode)

    def cmp_files(src: FileInfo, dst: FileInfo) -> bool:
        """Fast compare two files."""
        bufsize = 8 * 1024
        with open(src.path, "rb") as fp1, open(dst.path, "rb") as fp2:
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
        return (
            dst.stat is None
            or stat.S_IFMT(src.stat.st_mode) != stat.S_IFMT(dst.stat.st_mode)
            or (
                preserve_timestamps
                and abs(src.stat.st_mtime - dst.stat.st_mtime) > 0.001
            )
            or src.stat.st_size != dst.stat.st_size
            or (not preserve_timestamps and isfile(src) and not cmp_files(src, dst))
            or src.basename != dst.basename
        )

    def copystat(src: FileInfo, dst: FileInfo) -> None:
        """Update attribute of dst file with src attributes.

        :param src: the source FileInfo object
        :param dst: the target FileInfo object
        """
        if islink(src):  # windows: no cover
            mode = stat.S_IMODE(src.stat.st_mode)
            if hasattr(os, "lchmod"):
                os.lchmod(dst.path, mode)

            if hasattr(os, "lchflags") and hasattr(src.stat, "st_flags"):
                try:
                    os.lchflags(dst.path, src.stat.st_flags)
                except OSError as why:  # defensive code
                    import errno

                    if (
                        not hasattr(errno, "EOPNOTSUPP")
                        or why.errno != errno.EOPNOTSUPP
                    ):
                        raise
        else:
            mode = stat.S_IMODE(src.stat.st_mode)
            if hasattr(os, "utime"):
                if preserve_timestamps:
                    os.utime(dst.path, (src.stat.st_atime, src.stat.st_mtime))
                else:
                    os.utime(dst.path, None)
            if hasattr(os, "chmod"):
                os.chmod(dst.path, mode)
            if hasattr(os, "chflags") and hasattr(src.stat, "st_flags"):
                try:
                    os.chflags(dst.path, src.stat.st_flags)
                except OSError as why:  # defensive code
                    import errno

                    if (
                        not hasattr(errno, "EOPNOTSUPP")
                        or why.errno != errno.EOPNOTSUPP
                    ):
                        raise

    def safe_copy(src: FileInfo, dst: FileInfo) -> None:
        """Copy src file into dst preserving all attributes.

        :param src: the source FileInfo object
        :param dst: the target FileInfo object
        """
        if islink(src):  # windows: no cover
            linkto = os.readlink(src.path)
            if not islink(dst) or os.readlink(dst.path) != linkto:
                if dst.stat is not None:
                    rm(dst.path, recursive=True, glob=False)
                os.symlink(linkto, dst.path)
            copystat(src, dst)
        else:
            if isdir(dst):
                # dst directory will be replaced by a file having the same
                # content as 'src'
                rm(dst.path, recursive=True, glob=False)
            elif islink(dst):
                # dst symlink will be replaced by a file having the same
                #  content as 'src'
                rm(dst.path, recursive=False, glob=False)

            try:
                if dst.basename != src.basename:
                    rm(dst.path, glob=False)
                    dst = FileInfo(
                        os.path.join(os.path.dirname(dst.path), src.basename),
                        None,
                        src.basename,
                    )

                with open(src.path, "rb") as fsrc:
                    with open(dst.path, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst)
            except OSError:
                rm(dst.path, glob=False)
                with open(src.path, "rb") as fsrc:
                    with open(dst.path, "wb") as fdst:
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
                dest_dir = os.path.join(os.path.dirname(dst.path), src.basename)
            else:
                dest_dir = dst.path

            if isdir(dst):
                # For directories in case of non-matching casing just do a rename
                # This ensure sync_tree is efficient in case content of the directory
                # is similar between src and dst.
                if dst.basename != src.basename:
                    os.rename(dst.path, dest_dir)
            else:
                os.makedirs(dest_dir)
        except OSError:
            # in case of error to change parent directory
            # permissions. The permissions will be then
            # set correctly at the end of rsync.
            e3.os.fs.chmod("a+wx", os.path.dirname(dst.path))

            if isdir(dst):
                if dst.basename != src.basename:
                    os.rename(dst.path, dest_dir)
            else:
                os.makedirs(dest_dir)

    def walk(
        root_dir: str, target_root_dir: str, entry: Optional[FilesInfo] = None
    ) -> Iterable[FilesInfo]:
        """Walk through source and target file trees.

        :param root_dir: path to source tree
        :param target_root_dir: path to target tree
        :param entry: a FilesInfo object (used internally for the recursion)

        :return: an iterator that iterate other the relevant FilesInfo object
        """
        if entry is None:
            target_stat = None
            if os.path.exists(target_root_dir):
                target_stat = os.lstat(target_root_dir)

            entry = FilesInfo(
                "",
                FileInfo(root_dir, os.lstat(root_dir), ""),
                FileInfo(target_root_dir, target_stat, ""),
            )
            yield entry

        try:
            source_names = {path_key(k): k for k in os.listdir(entry.source.path)}
        except Exception:  # defensive code
            e3.log.debug("cannot get sources list", exc_info=True)
            # Don't crash in case a source directory cannot be read
            return

        target_names = {}
        if isdir(entry.target):
            try:
                target_names = {path_key(k): k for k in os.listdir(entry.target.path)}
            except Exception:
                e3.log.debug("cannot get targets list", exc_info=True)
                target_names = {}

        all_names = set(source_names.keys()) | set(target_names.keys())

        result = []
        for name in all_names:
            rel_path = f"{entry.rel_path}/{name}"

            source_full_path = os.path.join(
                entry.source.path, source_names.get(name, name)
            )
            target_full_path = os.path.join(
                entry.target.path, target_names.get(name, name)
            )
            source_stat = None
            target_stat = None

            if name in source_names:
                source_stat = os.lstat(source_full_path)

            source_file = FileInfo(
                source_full_path, source_stat, os.path.basename(source_full_path)
            )

            if name in target_names:
                target_stat = os.lstat(target_full_path)

            target_file = FileInfo(
                target_full_path, target_stat, os.path.basename(target_full_path)
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

    if not os.path.exists(source):
        raise FSError(origin="sync_tree", message=f"{source} does not exist")

    # Keep track of deleted and updated files
    deleted_list: List[str] = []
    updated_list: List[str] = []

    for wf in walk(source_top, target_top):
        if wf.source.stat is None and wf.target.stat is not None:
            # Entry that exist only in the target file tree. Check if we
            # should delete it
            if delete:
                rm(wf.target.path, recursive=True, glob=False)
                deleted_list.append(wf.target.path)
        else:
            # At this stage we have an element to synchronize in
            # the source tree.
            if need_update(wf.source, wf.target):
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


def extension(path: str) -> str:
    """Return the extension of a given filename.

    Contrary to os.path.splitext which returns .gz, the function will return
    .tar.gz if the file is FILENAME.tar.gz.

    :param path: a path
    :return: an extension
    """
    root, ext = os.path.splitext(path)
    _, ext2 = os.path.splitext(root)
    if ext2 == ".tar":
        return ext2 + ext
    else:
        return ext
