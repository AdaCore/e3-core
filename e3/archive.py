"""Support for reading and writing tar and zip archives."""
from __future__ import absolute_import
from __future__ import print_function

from contextlib import closing
import fnmatch
import os
import subprocess
import sys
import tempfile

import e3
import e3.error
import e3.fs
import e3.log
import e3.os.fs
from e3.os.process import Run

logger = e3.log.getLogger('archive')


class ArchiveError(e3.error.E3Error):
    pass


def __select_archiving_tool(filename, unpack=True,
                            tar='tar',
                            force_extension=None,
                            require_wilcard=False):
    """Internal function used by create_archive and unpack_archive.

    :param filename: the name of the archive to extract the extension
    :type filename: str
    :param unpack: to know if we are called by unpack_archive or create_archive
    :type unpack: bool
    :param tar: path to the tar binary to use ('tar' by default)
    :type tar: str
    :param force_extension: specify the archive extension if not in the
        filename
    :type force_extension: str | None
    :param require_wilcard: whether wildcard will be used, in that case we try
        to use the python libraries directly to avoid portability issues
    :type require_wilcard: bool

    :return: a tuple (ext, True if we should use python libraries else False)
    :rtype: (str, bool)
    """
    def has_python_lib_support(archive_ext):
        """Return True if python library can be used.

        :type archive_ext: str
        :rtype: bool
        """
        if archive_ext == 'zip':
            # We need to check for zlib presence to be sure that we can
            # compress otherwise zipfile will be used a an archiver
            # (no compression)
            try:
                import zlib
            except ImportError:
                zlib = None
            return zlib is not None
        else:
            try:
                import tarfile
            except ImportError:
                tarfile = None
            return tarfile is not None

    def has_binary_tools(archive_ext):
        """Return True if binary tools ar found else False.

        :type archive_ext: str
        :rtype: bool
        """
        if not e3.os.fs.which(tar):
            return False
        elif archive_ext == 'tar.gz' and not e3.os.fs.which('gzip'):
            return False
        elif archive_ext == 'tar.bz2' and not e3.os.fs.which(
                'bunzip' if unpack else 'bzip2'):
            return False
        elif archive_ext == 'zip' and not e3.os.fs.which(
                'unzip' if unpack else 'zip'):
            return False
        return True

    # Check extension
    if filename.endswith('.tar.gz') or filename.endswith('.tgz') or (
            force_extension is not None and
            force_extension in ['.tar.gz', '.tgz']):
        ext = 'tar.gz'
    elif filename.endswith('.tar.bz2') or (
            force_extension is not None and
            force_extension == '.tar.bz2'):
        ext = 'tar.bz2'
    elif filename.endswith('.tar') or (
            force_extension is not None and
            force_extension == '.tar'):
        ext = 'tar'
    elif filename.endswith('.zip') or (
            force_extension is not None and
            force_extension == '.zip'):
        ext = 'zip'
    else:
        raise ArchiveError(origin='unpack_archive',
                           message='unknown format "%s"' % filename)

    if sys.platform == 'win32' or require_wilcard:
        # On windows, do not spawn tar/zip often provided by cygwin but calls
        # tarfile/zipfile python implementation.  If wildcards (* or ?) are
        # used in selected_files, to avoid portability issue, use directly the
        # python library if possible
        impls = (has_python_lib_support, has_binary_tools)
    else:
        impls = (has_binary_tools, has_python_lib_support)

    for imp in impls:
        if imp(ext):
            return ext, imp == has_python_lib_support

    raise ArchiveError(
        origin='unpack_archive',
        message='no python module and no binary tools found')


def unpack_archive(filename,
                   dest,
                   selected_files=None,
                   remove_root_dir=False,
                   tar='tar',
                   unpack_cmd=None,
                   force_extension=None,
                   delete=False,
                   ignore=None,
                   preserve_timestamps=True):
    """Unpack an archive file (.tgz, .tar.gz, .tar or .zip).

    :param filename: archive to unpack
    :type filename: str
    :param dest: destination directory (should exist)
    :type dest: str
    :param selected_files: list of files to unpack (partial extraction). If
        None all files are unpacked
    :type selected_files: collections.iterable[str] | None
    :param remove_root_dir: if True then the root dir of the archive is
        suppressed.
        if set to 'auto' then the root dir of the archive is suppressed only
        if it is possible. If not do not raise an exception in that case and
        fallback on the other method.
    :type remove_root_dir: bool
    :param tar: path/to/tar binary (else use 'tar')
    :type tar: str
    :param unpack_cmd: command to run to unpack the archive, if None use
        default methods or raise ArchiveError if archive format is not
        supported. If unpack_cmd is not None, then remove_root_dir is ignored.
        The unpack_cmd must raise ArchiveError in case of failure.
    :type unpack_cmd: callable | None
    :param force_extension: specify the archive extension if not in the
        filename. If filename has no extension and force_extension is None
        unpack_archive will fail.
    :type force_extension: str | None
    :param delete: if True and remove_root_dir is also True, remove files
        from dest if they do not exist in the archive
    :type delete: bool
    :param ignore: a list of files/folders to keep when synchronizing with
        the final destination directory.
    :type ignore: list[str] | None
    :param preserve_timestamps: if False and remove_root_dir is True, and the
        target directory exists, ensure that updated files get their timestamp
        updated to current time.
    :type preserve_timestamps: bool

    :raise ArchiveError: in case of error

    cygpath (win32) utilities might be needed when using remove_root_dir option
    """
    logger.debug('unpack %s in %s' % (filename, dest))
    # First do some checks such as archive existence or destination directory
    # existence.
    if not os.path.isfile(filename):
        raise ArchiveError(origin='unpack_archive',
                           message='cannot find %s' % filename)

    if not os.path.isdir(dest):
        raise ArchiveError(origin='unpack_archive',
                           message='dest dir %s does not exist' % dest)

    if selected_files is None:
        selected_files = []

    # We need to resolve to an absolute path as the extraction related
    # processes will be run in the destination directory
    filename = os.path.abspath(filename)

    if unpack_cmd is not None:
        # Use user defined unpack command
        if not selected_files:
            return unpack_cmd(filename, dest)
        else:
            return unpack_cmd(filename, dest,
                              selected_files=selected_files)

    if [f for f in selected_files if '*' in f or '?' in f]:
        require_wilcard = True
    else:
        require_wilcard = False

    ext, use_python_lib = __select_archiving_tool(
        filename,
        unpack=True,
        tar=tar,
        force_extension=force_extension,
        require_wilcard=require_wilcard)

    # If remove_root_dir is set then extract to a temp directory first.
    # Otherwise extract directly to the final destination
    if remove_root_dir:
        tmp_dest = tempfile.mkdtemp(
            prefix='',
            dir=os.path.dirname(os.path.abspath(dest)))
    else:
        tmp_dest = dest

    try:
        if use_python_lib:
            if ext in ('tar', 'tar.bz2', 'tar.gz'):
                import tarfile
                try:
                    with closing(tarfile.open(filename, mode='r')) as fd:
                        # selected_files must be converted to tarfile members
                        if selected_files:
                            members = fd.getmembers()

                            def is_matched(tarfile_members, pattern):
                                """Return a list of matched tarfile members.

                                :param tarfile_members: TarInfo list
                                :type tarfile_members: list[TarInfo]
                                :param pattern: string or regexp
                                :type pattern: str

                                :raise ArchiveError: if no member match the
                                    pattern.

                                :return: a list of tarfile members
                                :rtype: list[TarInfo]
                                """
                                r = [mem for mem in tarfile_members
                                     if fnmatch.fnmatch(mem.name, pattern)]
                                if not r:
                                    raise ArchiveError(
                                        'unpack_archive',
                                        'Cannot untar %s ' % pattern)
                                return r

                            selected_files = [f for l in selected_files
                                              for f in is_matched(members, l)]

                        # detect directories. This is not done by default
                        # For each directory, select all the tree
                        selected_dirnames = [
                            d.name for d in selected_files if d.isdir()]
                        for dname in selected_dirnames:
                            selected_files += [
                                fd.getmember(n) for n in fd.getnames()
                                if n.startswith(dname + '/')]
                        fd.extractall(tmp_dest,
                                      selected_files if selected_files
                                      else None)

                except tarfile.TarError as e:
                    raise ArchiveError(
                        origin='unpack_archive',
                        message='Cannot untar %s (%s)' % (filename, e)), \
                        None, sys.exc_traceback

            else:
                import zipfile
                try:
                    with closing(zipfile.ZipFile(filename, mode='r')) as fd:
                        fd.extractall(tmp_dest,
                                      selected_files if selected_files
                                      else None)
                except zipfile.BadZipfile as e:
                    raise ArchiveError(
                        origin='unpack_archive',
                        message='Cannot unzip %s (%s)' % (filename, e)), \
                        None, sys.exc_traceback

        else:
            # Spawn tar, gzip, bunzip2 or zip

            if ext == 'tar.gz':
                p = Run([['gzip', '-dc', filename],
                         [tar, '-xf', '-'] + list(selected_files)],
                        cwd=tmp_dest)
            elif ext == 'tar.bz2':
                p = Run([['bunzip2', '-dc', filename],
                         [tar, '-xf', '-'] + list(selected_files)],
                        cwd=tmp_dest)
            elif ext == 'tar':
                p = Run([tar, '-xf', filename] + list(selected_files),
                        cwd=tmp_dest)
            else:
                p = Run(['unzip', '-o', filename] + list(selected_files),
                        cwd=tmp_dest)

            if p.status != 0:
                # The extract command failed
                raise ArchiveError(origin='unpack_archive',
                                   message='extraction of %s failed:\n%s' % (
                                       filename, p.out))

        if remove_root_dir:
            # First check that we have only one dir in our temp destination,
            # and no other files or directories. If not raise an error.
            nb_files = len(os.listdir(tmp_dest))
            if nb_files == 0:
                # Nothing to do...
                return
            if nb_files > 1:
                if remove_root_dir != 'auto':
                    raise ArchiveError(
                        origin='unpack_archive',
                        message='archive does not have a unique root dir')

                # We cannot remove root dir but remove_root_dir is set to
                # 'auto' so fallback on non remove_root_dir method
                if not os.listdir(dest):
                    e3.fs.mv(os.path.join(tmp_dest, '*'), dest)
                else:
                    e3.fs.sync_tree(
                        tmp_dest, dest, delete=delete,
                        ignore=ignore,
                        preserve_timestamps=preserve_timestamps)
            else:
                root_dir = os.path.join(tmp_dest, os.listdir(tmp_dest)[0])

                # Now check if the destination directory is empty. If this is
                # the case a simple move will work, otherwise we need to do a
                # sync_tree (which cost more)

                if not os.listdir(dest):
                    e3.fs.mv([os.path.join(root_dir, f)
                              for f in os.listdir(root_dir)], dest)
                else:
                    e3.fs.sync_tree(root_dir, dest, delete=delete,
                                    ignore=ignore,
                                    preserve_timestamps=preserve_timestamps)

    finally:
        # Always remove the temp directory before exiting
        if remove_root_dir:
            e3.fs.rm(tmp_dest, True)


def create_archive(filename, from_dir, dest, tar='tar', force_extension=None,
                   from_dir_rename=None, no_root_dir=False):
    """Create an archive file (.tgz, .tar.gz, .tar or .zip).

    On Windows, if the python tarfile and zipfile modules are available, the
    python implementation is used to create the archive.  On others system,
    create_archive spawn tar, gzip or zip as it is twice faster that the python
    implementation. If the tar, gzip or zip binary is not found, the python
    implementation is used.

    :param filename: archive to create
    :type filename: str
    :param from_dir: directory to pack (full path)
    :type from_dir: str
    :param dest: destination directory (should exist)
    :type dest: str
    :param tar: path/to/tar binary (else use 'tar')
    :type tar: str
    :param force_extension: specify the archive extension if not in the
        filename. If filename has no extension and force_extension is None
        create_archive will fail.
    :type force_extension: str | None
    :param from_dir_rename: name of root directory in the archive.
    :type from_dir_rename: str | None
    :param no_root_dir: create archive without the root dir (zip only)
    :type no_root_dir: bool

    :raise ArchiveError: if an error occurs
    """
    # Check extension
    from_dir = from_dir.rstrip('/')
    filepath = os.path.abspath(os.path.join(dest, filename))

    ext, use_python_lib = __select_archiving_tool(
        filename,
        unpack=False,
        force_extension=force_extension)

    if use_python_lib:
        if from_dir_rename is None:
            from_dir_rename = os.path.basename(from_dir)

        if ext == 'zip':
            import zipfile
            archive = zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED)
            for root, _, files in os.walk(from_dir):
                relative_root = os.path.relpath(os.path.abspath(root),
                                                os.path.abspath(from_dir))
                for f in files:
                    zip_file_path = os.path.join(
                        from_dir_rename, relative_root, f)
                    if no_root_dir:
                        zip_file_path = os.path.join(relative_root, f)
                    archive.write(os.path.join(root, f),
                                  zip_file_path)
            archive.close()
            return
        else:
            import tarfile
            if ext == 'tar':
                tar_format = 'w'
            elif ext == 'tar.gz':
                tar_format = 'w:gz'
            else:
                raise ArchiveError(origin='create_archive',
                                   message='unsupported ext %s' % ext)
            archive = tarfile.open(filepath, tar_format)
            archive.add(from_dir, from_dir_rename, recursive=True)
            archive.close()
    else:
        command_dir = os.path.dirname(from_dir)
        base_archive_dir = os.path.basename(from_dir)
        abs_archive_dir = from_dir

        if from_dir_rename is not None:
            base_archive_dir = from_dir_rename
            abs_archive_dir = os.path.join(command_dir, base_archive_dir)

            if os.path.isdir(abs_archive_dir):
                raise ArchiveError(
                    origin='create_archive',
                    message='%s should not exist' % abs_archive_dir)
            e3.os.fs.mv(from_dir, abs_archive_dir)

        try:
            if ext == 'tar.gz':
                p = Run([[tar, 'cf', '-', base_archive_dir],
                         ['gzip', '-9']],
                        output=filepath,
                        error=subprocess.PIPE,
                        cwd=command_dir)
            elif ext == 'tar':
                p = Run([tar, 'cf', '-', base_archive_dir],
                        output=filepath,
                        error=subprocess.PIPE,
                        cwd=command_dir)
            elif ext == 'zip':
                if no_root_dir:
                    p = Run(['zip', '-r9', '-q', filepath,
                             '.', '-i', '*'],
                            cwd=os.path.join(command_dir, base_archive_dir))
                else:
                    p = Run(['zip', '-r9', '-q', filepath, base_archive_dir],
                            cwd=command_dir)
            else:
                raise ArchiveError(
                    origin='create_archive',
                    message='unsupported ext %s' % ext)
            if p.status != 0:
                raise ArchiveError(
                    origin='create_archive',
                    message='creation of %s failed:\n%s' % (
                        filename, p.out))
        finally:
            if from_dir_rename is not None:
                e3.os.fs.mv(abs_archive_dir, from_dir)