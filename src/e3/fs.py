"""High-Level file manipulation."""


import fnmatch
import glob
import hashlib
import itertools
import os
import shutil
import stat
import sys
from collections import namedtuple

import e3
import e3.error
import e3.log
import e3.os.fs

logger = e3.log.getLogger("fs")


class FSError(e3.error.E3Error):
    pass


def cp(source, target, copy_attrs=True, recursive=False, preserve_symlinks=False):
    """Copy files.

    :param str source: a glob pattern
    :param str target: target file or directory. If the source resolves as
        several files then target should be a directory
    :param bool copy_attrs: If True, also copy all the file attributes such as
        mode, timestamps, ownership, etc.
    :param bool recursive: If True, recursive copy. This also preserves
        attributes; if copy_attrs is False, a warning is emitted.
    :param bool preserve_symlinks: if True symlinks are recreated in the
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
        raise FSError(origin="cp", message='can\'t find files matching "%s"' % source)
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
                origin="cp", message="error occurred while copying %s" % f
            ).with_traceback(sys.exc_info()[2])


def directory_content(path, include_root_dir=False, unixpath=False):
    """Return the complete directory content (recusrsively).

    :param path: path for the which the content should be returned
    :type path: str
    :param include_root_dir: if True include the root directory in the paths
        returned by the function. Otherwise return relative paths
    :type include_root_dir: bool
    :param unixpath: if True return unix compatible paths (calling unixpath on
        all elements returned
    :type unixpath: bool
    :return: a list of of path. Note that directories will end with a path
        separator
    :rtype: list[str]
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


def echo_to_file(filename, content, append=False):
    """Output content into a file.

    This function is useful when writing few content to a file for which we
    don't want to keep a file descriptor opened . In other cases, it's more
    efficient to open a file and use the regular python I/O functions.

    :param filename: file to write into
    :type filename: str
    :param content: string to be written
    :type content: str | list[str]
    :param append: if True append to the file, otherwise overwrite.
    :type append: bool
    """
    with open(filename, "a+" if append else "w+") as fd:
        if append:
            fd.seek(0, 2)

        if isinstance(content, list):
            for l in content:
                fd.write(l + "\n")
        else:
            fd.write(content)


def find(
    root, pattern=None, include_dirs=False, include_files=True, follow_symlinks=False
):
    """Find files or directory recursively.

    :param root: directory from which the research start
    :type root: str
    :param pattern: glob pattern that files or directories should match in
        order to be included in the final result
    :type pattern: str | None
    :param include_dirs: if True include directories
    :type include_dirs: bool
    :param include_files: if True include regular files
    :type include_files: bool
    :param follow_symlinks: if True include symbolic links
    :type follow_symlinks: bool

    :return: a list of files
    :rtype: list[str]
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


def get_filetree_state(path, ignore_hidden=True):
    """Compute a hash on a filetree to reflect its current state.

    :param path: root path of the file tree to be checked
    :type path: str
    :param ignore_hidden: if True (default) then files and directories
        tarting with a dot are ignored.
    :type ignore_hidden: bool
    :return: a hash as a string
    :rtype: str

    The function will not report changes in the hash if a file is modified
    and its attributes (size, modification time and mode) are not changed.
    This case is quite uncommon. By ignoring it we can compute efficiently a
    hash representing the state of the file tree without having to read the
    content of all files.
    """

    def compute_state(file_path):
        f_stat = os.lstat(file_path)

        state = ":".join(
            [file_path, str(f_stat.st_mode), str(f_stat.st_size), str(f_stat.st_mtime)]
        )
        if isinstance(file_path, str):
            # Make sure to encode unicode objects before hashing
            return state.encode("utf-8")
        else:
            return state

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


def ls(path, emit_log_record=True):
    """List files.

    :param path: glob pattern or glob pattern list
    :type path: list[string] | string
    :param emit_log_record: if True, emit a log (debug) record
    :type emit_log_record: bool

    :return: a list of filenames
    :rtype: list[string]

    This function do not raise an error if no file matching the glob pattern
    is encountered. The only consequence is that an empty list is returned.
    """
    if isinstance(path, str):
        path = (path,)
    else:
        path = list(path)

    if emit_log_record:
        logger.debug("ls %s", " ".join(path))

    return list(sorted(itertools.chain.from_iterable((glob.glob(p) for p in path))))


def mkdir(path, mode=0o755, quiet=False):
    """Create a directory.

    :param path: path to create. If intermediate directories do not exist
        the procedure create them
    :type path: str
    :param mode: default is 0755
    :type mode: int
    :param quiet: whether a log record should be emitted when creating the
        directory
    :type quiet: bool
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
                origin="mkdir", message="can't create %s" % path
            ).with_traceback(sys.exc_info()[2])


def mv(source, target):
    """Move files.

    :param source: a glob pattern
    :type source: str | list[str]
    :param target: target file or directory. If the source resolves as
        several files then target should be a directory
    :type target: str

    :raise FSError: if an error occurs
    """

    def move_file(src, dst):
        """Reimplementation of shutil.move.

        The implementation follows shutil.move from the standard library.
        The only difference is that we use e3.fs.rm function instead of
        rmtree. This ensure moving a directory with read-only files will
        work.
        """

        def same_file(src, dst):
            if hasattr(os.path, "samefile"):
                try:
                    return os.path.samefile(src, dst)
                except OSError:
                    return False
            return os.path.normcase(os.path.abspath(src)) == os.path.normcase(
                os.path.abspath(dst)
            )

        def basename(path):
            sep = os.path.sep + (os.path.altsep or "")
            return os.path.basename(path.rstrip(sep))

        def destinsrc(src, dst):
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
                raise FSError("Destination path '%s' already exists" % real_dst)
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
                        "Cannot move a directory '%s' into itself" " '%s'." % (src, dst)
                    )
                shutil.copytree(src, real_dst, symlinks=True)
                rm(src, recursive=True)
            else:
                shutil.copy2(src, real_dst)
                rm(src)
        return real_dst

    if isinstance(source, str):
        logger.debug("mv %s %s", source, target)
    else:
        logger.debug("mv %s %s", " ".join(source), target)

    try:
        # Compute file list and number of file to copy
        file_list = ls(source, emit_log_record=False)
        nb_files = len(file_list)

        if nb_files == 0:
            raise FSError(
                origin="mv", message='cannot find files matching "%s"' % source
            )
        elif nb_files == 1:
            source = file_list[0]
            if os.path.isdir(source) and os.path.isdir(target):
                move_file(source, os.path.join(target, os.path.basename(source)))
            else:
                move_file(source, target)
        elif not os.path.isdir(target):
            # More than one file to move but the target is not a directory
            raise FSError("mv", "%s should be a directory" % target)
        else:
            for f in file_list:
                f_dest = os.path.join(target, os.path.basename(f))
                e3.log.debug("mv %s %s", f, f_dest)
                move_file(f, f_dest)
    except Exception as e:
        logger.error(e)
        raise FSError(origin="mv", message=str(e)).with_traceback(sys.exc_info()[2])


def rm(path, recursive=False, glob=True):
    """Remove files.

    :param path: a glob pattern, or a list of glob patterns
    :type path: str | list[str]
    :param bool recursive: if True do a recursive deletion. Default is False
    :param bool glob: if True globbing pattern expansion is used

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

    def onerror(func, error_path, exc_info):
        """When shutil.rmtree fail, try again to delete the file.

        :param func: function to call on error
        :type func: () -> None
        :param error_path: file or directory to remove
        :type error_path: str
        :param exc_info: exception raised when the first delete attempt was
             made
        :type exc_info: tuple
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
                origin="rm", message="error occurred while removing %s" % f
            ).with_traceback(sys.exc_info()[2])


def splitall(path):
    """Split a path into a list of path components.

    :param path: path to split
    :type path: str
    :return: a list of path components
    :rtype: tuple[str]
    """
    dirnames = []
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
    source,
    target,
    ignore=None,
    file_list=None,
    delete=True,
    preserve_timestamps=True,
    delete_ignore=False,
):
    """Synchronize the files and directories between two directories.

    :param source: the directory from where the files and directories
        need to be copied
    :type source: str
    :param target: the target directory
    :type target: str
    :param ignore: glob pattern or list of files or directories to ignore,
        if the name starts with `/` then only the path is taken into
        account from the root of the source (or target) directory.
        If the ignore value contains a glob pattern, it is taken in account
        only if it doesn't contain a /, since for now the filtering
        is not segmented by '/'.
    :type ignore: None | str | iterable[str]
    :param file_list: list of files to synchronize, if empty synchronize all
        files. Note that if file in the list is a directory then the complete
        content of that directory is included. Note also that ignore list
        takes precedence other file_list.
    :type file_list: None | list[str]
    :param delete: if True, remove files from target if they do not exist
        in source
    :type delete: bool
    :param preserve_timestamps: if True preserve original timestamps.
        If False updated files get their timestamps set to current time.
    :type preserve_timestamps: bool
    :param delete_ignore: if True files that are explicitely ignored
        are deleted. Note delete should be set to True in that case.
    :type delete_ignore: bool
    """
    # Some structure used when walking the trees to be synched
    FilesInfo = namedtuple("FilesInfo", ["rel_path", "source", "target"])
    FileInfo = namedtuple("FileInfo", ["path", "stat"])

    # normalize the list of file to synchronize
    norm_file_list = None
    if file_list is not None:
        norm_file_list = [wf.replace("\\", "/").rstrip("/") for wf in file_list]

    # normalize ignore patterns
    if ignore is not None:
        norm_ignore_list = [fn.replace("\\", "/") for fn in ignore]
        abs_ignore_patterns = [fn for fn in norm_ignore_list if fn.startswith("/")]
        rel_ignore_patterns = [fn for fn in norm_ignore_list if not fn.startswith("/")]

    def is_in_ignore_list(p):
        """Check if a file should be ignored.

        :param p: path relative to source directory (note it starts with a /)
        :type p: str

        :return: True if in the list of file to include
        :rtype: bool
        """
        if ignore is None:
            return False

        return (
            any((f for f in abs_ignore_patterns if p == f or p.startswith(f + "/")))
            or any(
                (f for f in rel_ignore_patterns if p[1:] == f or p.endswith("/" + f))
            )
            or any(
                (
                    f
                    for f in norm_ignore_list
                    if "/" not in f and fnmatch.fnmatch(os.path.basename(p), f)
                )
            )
        )

    def is_in_file_list(p):
        """Check if a file should be included.

        :param p: path relative to source directory (note it starts with a /)
        :type p: str

        :return: True if in the list of file to include
        :rtype: bool
        """
        return file_list is None or any(
            [
                f
                for f in norm_file_list
                if f == p[1:]
                or p.startswith("/" + f + "/")
                or f.startswith(p[1:] + "/")
            ]
        )

    def isdir(fi):
        """Check if a file is a directory.

        :param fi: a FileInfo namedtuple
        :type fi: FileInfo

        :return: True if fi is a directory
        :rtype: bool
        """
        return fi.stat is not None and stat.S_ISDIR(fi.stat.st_mode)

    def islink(fi):
        """Check if a file is a link.

        :param fi: a FileInfo namedtuple
        :type fi: FileInfo

        :return: True if fi is a symbolic link
        :rtype: bool
        """
        return fi.stat is not None and stat.S_ISLNK(fi.stat.st_mode)

    def isfile(fi):
        """Check if a file is a regular file.

        :param fi: a FileInfo namedtuple
        :type fi: FileInfo
        :return: True if fi is a regular file
        :rtype: bool
        """
        return fi.stat is not None and stat.S_ISREG(fi.stat.st_mode)

    def cmp_files(src, dst):
        """Fast compare two files.

        :type src: FileInfo
        :type dst: FileInfo
        """
        bufsize = 8 * 1024
        with open(src.path, "rb") as fp1, open(dst.path, "rb") as fp2:
            while True:
                b1 = fp1.read(bufsize)
                b2 = fp2.read(bufsize)
                if b1 != b2:
                    return False

                if len(b1) < bufsize:
                    return True

    def need_update(src, dst):
        """Check if dst file should updated.

        :param src: the source FileInfo object
        :type src: FileInfo
        :param dst: the target FileInfo object
        :type dst: FileInfo

        :return: True if we should update dst
        :rtype: bool
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
        )

    def copystat(src, dst):
        """Update attribute of dst file with src attributes.

        :param src: the source FileInfo object
        :type src: FileInfo
        :param dst: the target FileInfo object
        :type dst: FileInfo
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

    def safe_copy(src, dst):
        """Copy src file into dst preserving all attributes.

        :param src: the source FileInfo object
        :type src: FileInfo
        :param dst: the target FileInfo object
        :type dst: FileInfo
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
                with open(src.path, "rb") as fsrc:
                    with open(dst.path, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst)
            except IOError:
                rm(dst.path, glob=False)
                with open(src.path, "rb") as fsrc:
                    with open(dst.path, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst)
            copystat(src, dst)

    def safe_mkdir(dst):
        """Create a directory modifying parent directory permissions if needed.

        :param dst: directory to create
        :type dst: FileInfo
        """
        try:
            os.makedirs(dst.path)
        except OSError:
            # in case of error to change parent directory
            # permissions. The permissions will be then
            # set correctly at the end of rsync.
            e3.os.fs.chmod("a+wx", os.path.dirname(dst.path))
            os.makedirs(dst.path)

    def walk(root_dir, target_root_dir, entry=None):
        """Walk through source and target file trees.

        :param root_dir: path to source tree
        :type root_dir: str
        :param target_root_dir: path to target tree
        :type target_root_dir: str
        :param entry: a FilesInfo object (used internally for the recursion)
        :type entry: FilesInfo

        :return: an iterator that iterate other the relevant FilesInfo object
        :rtype: collections.iterable(FilesInfo)
        """
        if entry is None:
            target_stat = None
            if os.path.exists(target_root_dir):
                target_stat = os.lstat(target_root_dir)

            entry = FilesInfo(
                "",
                FileInfo(root_dir, os.lstat(root_dir)),
                FileInfo(target_root_dir, target_stat),
            )
            yield entry
        try:
            source_names = set(os.listdir(entry.source.path))
        except Exception:  # defensive code
            e3.log.debug("cannot get sources list", exc_info=True)
            # Don't crash in case a source directory cannot be read
            return

        target_names = set()
        if isdir(entry.target):
            try:
                target_names = set(os.listdir(entry.target.path))
            except Exception:
                e3.log.debug("cannot get targets list", exc_info=True)
                target_names = set()

        all_names = source_names | target_names

        result = []
        for name in all_names:
            rel_path = "%s/%s" % (entry.rel_path, name)

            source_full_path = os.path.join(entry.source.path, name)
            target_full_path = os.path.join(entry.target.path, name)
            source_stat = None
            target_stat = None

            if name in source_names:
                source_stat = os.lstat(source_full_path)

            source_file = FileInfo(source_full_path, source_stat)

            if name in target_names:
                target_stat = os.lstat(target_full_path)

            target_file = FileInfo(target_full_path, target_stat)
            result.append(FilesInfo(rel_path, source_file, target_file))

        for el in result:
            if is_in_ignore_list(el.rel_path):
                logger.debug("ignore %s", el.rel_path)
                if delete_ignore:
                    yield FilesInfo(
                        el.rel_path, FileInfo(el.source.path, None), el.target
                    )
            elif is_in_file_list(el.rel_path):
                yield el
                if isdir(el.source):
                    for x in walk(root_dir, target_root_dir, el):
                        yield x
            else:
                yield FilesInfo(el.rel_path, FileInfo(el.source.path, None), el.target)

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
        raise FSError(origin="sync_tree", message="%s does not exist" % source)

    # Keep track of deleted and updated files
    deleted_list = []
    updated_list = []

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
                    if isfile(wf.target) or islink(wf.target):
                        rm(wf.target.path, glob=False)
                    if not isdir(wf.target):
                        safe_mkdir(wf.target)
                        updated_list.append(wf.target.path)
                    copystat_dir_list.append((wf.source, wf.target))

    # Adjust directory permissions once all files have been copied
    for d in copystat_dir_list:
        copystat(d[0], d[1])

    return updated_list, deleted_list


def extension(path):
    """Return the extension of a given filename.

    Contrary to os.path.splitext which returns .gz, the function will return
    .tar.gz if the file is FILENAME.tar.gz.

    :param path: a path
    :type path: str
    :return: an extension
    :rtype: str
    """
    root, ext = os.path.splitext(path)
    _, ext2 = os.path.splitext(root)
    if ext2 == ".tar":
        return ext2 + ext
    else:
        return ext
