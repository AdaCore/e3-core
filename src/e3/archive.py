"""Support for reading and writing tar and zip archives."""

from __future__ import annotations

import fnmatch
import os
import sys
import tarfile
import tempfile
import zipfile
from contextlib import closing
from typing import TYPE_CHECKING, cast

import e3
import e3.error
import e3.fs
import e3.log
import e3.os.fs


if TYPE_CHECKING:
    from typing import Literal, Text, Union, IO, Any
    from collections.abc import Callable, Sequence
    from os import PathLike
    from e3.mypy import assert_never

    UnpackAutoRemoveDirType = Literal["auto"]
    RemoveRootDirType = Union[bool, Literal["auto"]]

    TAR_GZ = Literal["tar.gz"]
    TAR_BZ2 = Literal["tar.bz2"]
    TAR_XZ = Literal["tar.xz"]
    TAR = Literal["tar"]
    ZIP = Literal["zip"]

else:
    TAR_GZ = "tar.gz"
    TAR_BZ = "tar.bz2"
    TAR_XZ = "tar.xz"
    TAR = "tar"
    ZIP = "zip"

logger = e3.log.getLogger("archive")

if sys.platform == "win32":
    # On Windows force the executable bit on all files. This ensures that when
    # using cygwin unziped files get an executable bit set (the executable
    # does not exist in win32 but is simulated in Cygwin).

    class E3ZipInfo(zipfile.ZipInfo):
        @classmethod
        def from_file(cls, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = super().from_file(*args, **kwargs)
            result.external_attr = (0o555 << 16) | result.external_attr
            return result

    zipfile.ZipInfo = E3ZipInfo  # type: ignore[misc]


class E3ZipFile(zipfile.ZipFile):
    """Override default ZipFile with attributes preservation."""

    def _extract_member(
        self,
        member: Text | zipfile.ZipInfo,
        path: str | PathLike[str] | None,
        pwd: bytes | None,
    ) -> str:
        result = super()._extract_member(member, path, pwd)  # type: ignore

        if sys.platform != "win32":
            # Try to preserve attributes on non Windows platforms as
            # executable attribute is relevant on those platforms. As we rely
            # on an internal ignore any errors at this stage.
            try:
                # preserve bits 0-8 only: rwxrwxrwx
                # this come from a proposed patch on python.org
                # see: https://bugs.python.org/issue15795
                if not isinstance(member, zipfile.ZipInfo):
                    member = self.getinfo(member)
                attr = member.external_attr >> 16 & 0x1FF
                if attr != 0:
                    os.chmod(result, attr)
            except AttributeError:  # defensive code
                pass
        return result


class ArchiveError(e3.error.E3Error):
    pass


def is_known_archive_format(filename: str) -> bool:
    """Check if a given path is a supported archive format.

    :param filename: path
    :return: True if the path corresponding to a supported archive format
    """
    ext = e3.fs.extension(filename)
    return ext in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar", ".zip")


def check_type(
    filename: str, force_extension: str | None = None
) -> TAR_GZ | TAR_BZ2 | TAR_XZ | TAR | ZIP:
    """Return the archive extension.

    Internal function used by create_archive and unpack_archive.

    :param filename: the name of the archive to extract the extension
    :param force_extension: specify the archive extension if not in the
        filename

    :return: the file extension
    """
    # Check extension
    if (
        filename.endswith(".tar.gz")
        or filename.endswith(".tgz")
        or (force_extension is not None and force_extension in [".tar.gz", ".tgz"])
    ):
        return "tar.gz"
    elif filename.endswith(".tar.bz2") or (
        force_extension is not None and force_extension == ".tar.bz2"
    ):
        return "tar.bz2"
    elif filename.endswith(".tar.xz") or (
        force_extension is not None and force_extension == ".tar.xz"
    ):
        return "tar.xz"
    elif filename.endswith(".tar") or (
        force_extension is not None and force_extension == ".tar"
    ):
        return "tar"
    elif filename.endswith(".zip") or (
        force_extension is not None and force_extension == ".zip"
    ):
        return "zip"
    else:
        raise ArchiveError(
            origin="unpack_archive", message=f'unknown format "{filename}"'
        )


def unpack_archive(
    filename: str,
    dest: str,
    fileobj: IO[bytes] | None = None,
    selected_files: Sequence[str] | None = None,
    remove_root_dir: RemoveRootDirType = False,
    unpack_cmd: Callable[..., None] | None = None,
    force_extension: str | None = None,
    delete: bool = False,
    ignore: list[str] | None = None,
    preserve_timestamps: bool = True,
    tmp_dir_root: str | None = None,
) -> None:
    """Unpack an archive file (.tgz, .tar.gz, .tar or .zip).

    :param filename: archive to unpack
    :param dest: destination directory (should exist)
    :param fileobj: if specified, the archive is read from this file object
        instead of opening a file. The file object must be opened in binary
        mode. In this case filename is the name of the archive contained
        in the file object.
    :param selected_files: list of files to unpack (partial extraction). If
        None all files are unpacked
    :param remove_root_dir: if True then the root dir of the archive is
        suppressed.
        if set to 'auto' then the root dir of the archive is suppressed only
        if it is possible. If not do not raise an exception in that case and
        fallback on the other method.
    :param unpack_cmd: command to run to unpack the archive, if None use
        default methods or raise ArchiveError if archive format is not
        supported. If unpack_cmd is not None, then remove_root_dir is ignored.
        The unpack_cmd must raise ArchiveError in case of failure.
    :param force_extension: specify the archive extension if not in the
        filename. If filename has no extension and force_extension is None
        unpack_archive will fail.
    :param delete: if True and remove_root_dir is also True, remove files
        from dest if they do not exist in the archive
    :param ignore: a list of files/folders to keep when synchronizing with
        the final destination directory.
    :param preserve_timestamps: if False and remove_root_dir is True, and the
        target directory exists, ensure that updated files get their timestamp
        updated to current time.
    :param tmp_dir_root: If not None the temporary directory used to extract the
        archive will be created in tmp_dir_root directory. If None the temporary
        directory is created in the destination directory. This argument only
        has an effect when remove_root_dir is True.

    :raise ArchiveError: in case of error

    cygpath (win32) utilities might be needed when using remove_root_dir option
    """
    logger.debug("unpack %s in %s", filename, dest)
    # First do some checks such as archive existence or destination directory
    # existence.
    if fileobj is None and not os.path.isfile(filename):
        raise ArchiveError(origin="unpack_archive", message=f"cannot find {filename}")

    if not os.path.isdir(dest):
        raise ArchiveError(
            origin="unpack_archive", message=f"dest dir {dest} does not exist"
        )

    if selected_files is None:
        selected_files = []

    # We need to resolve to an absolute path as the extraction related
    # processes will be run in the destination directory
    if fileobj is None:
        filename = os.path.abspath(filename)

    if unpack_cmd is not None:
        # Use user defined unpack command
        kwargs: dict[str, Any] = {}
        if selected_files:
            kwargs["selected_files"] = selected_files

        if fileobj is not None:
            kwargs["fileobj"] = fileobj

        return unpack_cmd(filename, dest, **kwargs)

    ext = check_type(filename, force_extension=force_extension)

    # If remove_root_dir is set then extract to a temp directory first.
    # Otherwise extract directly to the final destination
    if remove_root_dir:
        if tmp_dir_root is None:
            tmp_dir_root = os.path.dirname(os.path.abspath(dest))
        tmp_dest = tempfile.mkdtemp(prefix="", dir=tmp_dir_root)
    else:
        tmp_dest = dest

    try:
        if ext == "tar" or ext == "tar.bz2" or ext == "tar.gz" or ext == "tar.xz":
            try:
                # Set the right mode
                mode = "r:"
                if ext.endswith("bz2"):
                    mode += "bz2"
                elif ext.endswith("gz"):
                    mode += "gz"
                elif ext.endswith("xz"):
                    mode += "xz"
                # Extract tar files
                with closing(
                    tarfile.open(
                        filename if fileobj is None else None,
                        fileobj=fileobj,
                        mode=mode,
                    )
                ) as fd:
                    check_selected = set(selected_files)

                    def is_match(name: str, files: Sequence[str]) -> bool:
                        """check if name match any of the expression in files.

                        :param name: file name
                        :param files: list of patterns to test against
                        :return: True when the name is matched
                        """
                        for pattern in files:
                            if fnmatch.fnmatch(name, pattern):
                                if pattern in check_selected:
                                    check_selected.remove(pattern)
                                return True
                        return False

                    dirs: list[str] = []

                    # IMPORTANT: don't use the method extract. Always use the
                    # extractall function. Indeed extractall will set file
                    # permissions only once all selected members are unpacked.
                    # Using extract can lead to permission denied for example
                    # if a read-only directory is created.
                    if selected_files:
                        member_list = []
                        for tinfo in fd:
                            if is_match(
                                tinfo.name, selected_files
                            ) or tinfo.name.startswith(tuple(dirs)):
                                # If dir then add it for recursive extracting
                                if tinfo.isdir() and not tinfo.name.startswith(
                                    tuple(dirs)
                                ):
                                    dirs.append(tinfo.name)
                                member_list.append(tinfo)

                        if check_selected:
                            raise ArchiveError(
                                "unpack_archive", f"Cannot untar {filename} "
                            )

                        fd.extractall(path=tmp_dest, members=member_list)
                    else:
                        fd.extractall(path=tmp_dest)

            except tarfile.TarError as e:
                raise ArchiveError(
                    origin="unpack_archive",
                    message=f"Cannot untar {filename} ({e})",
                ) from e

        elif ext == "zip":
            try:
                with closing(
                    E3ZipFile(fileobj if fileobj is not None else filename, mode="r")
                ) as zip_fd:
                    zip_fd.extractall(
                        tmp_dest, selected_files if selected_files else None
                    )
            except zipfile.BadZipfile as e:
                raise ArchiveError(
                    origin="unpack_archive",
                    message=f"Cannot unzip {filename} ({e})",
                ) from e
        else:
            assert_never()

        if remove_root_dir:
            # First check that we have only one dir in our temp destination,
            # and no other files or directories. If not raise an error.
            nb_files = len(os.listdir(tmp_dest))
            if nb_files == 0:
                # Nothing to do...
                return
            if nb_files > 1:
                if remove_root_dir != "auto":
                    raise ArchiveError(
                        origin="unpack_archive",
                        message="archive does not have a unique root dir",
                    )

                # We cannot remove root dir but remove_root_dir is set to
                # 'auto' so fallback on non remove_root_dir method
                if not os.listdir(dest):
                    e3.fs.mv(os.path.join(tmp_dest, "*"), dest)
                else:
                    e3.fs.sync_tree(
                        tmp_dest,
                        dest,
                        delete=delete,
                        ignore=ignore,
                        preserve_timestamps=preserve_timestamps,
                    )
            else:
                root_dir = os.path.join(tmp_dest, os.listdir(tmp_dest)[0])

                # Now check if the destination directory is empty. If this is
                # the case a simple move will work, otherwise we need to do a
                # sync_tree (which cost more)

                if not os.listdir(dest):
                    e3.fs.mv(
                        [os.path.join(root_dir, f) for f in os.listdir(root_dir)], dest
                    )
                else:
                    e3.fs.sync_tree(
                        root_dir,
                        dest,
                        delete=delete,
                        ignore=ignore,
                        preserve_timestamps=preserve_timestamps,
                    )

    finally:
        # Always remove the temp directory before exiting
        if remove_root_dir:
            e3.fs.rm(tmp_dest, True)


def create_archive(
    filename: str,
    from_dir: str,
    dest: str | None = None,
    fileobj: IO[bytes] | None = None,
    force_extension: str | None = None,
    from_dir_rename: str | None = None,
    no_root_dir: bool = False,
) -> None:
    """Create an archive file (.tgz, .tar.gz, .tar or .zip).

    The Python implementations (tarfile and zipfile) are used on all platforms.
    Spawning tar, gzip or zip on Linux could be faster, however it has the
    disadvantage of not using the same implementation across platforms, hence
    the choice to only use the Python implementations.

    :param filename: archive to create
    :param from_dir: directory to pack (full path)
    :param dest: destination directory (should exist). If not specified,
        the archive is written to the file object passed with fileobj.
    :param fileobj: if specified, the archive is written to this file object
        instead of opening a file. The file object must be opened in binary
        mode. In this case filename is the name of the archive contained
        in the file object.
    :param force_extension: specify the archive extension if not in the
        filename. If filename has no extension and force_extension is None
        create_archive will fail.
    :param from_dir_rename: name of root directory in the archive.
    :param no_root_dir: create archive without the root dir (zip only)

    :raise ValueError: neither dest nor fileobj is provided
    :raise ArchiveError: if an error occurs
    """
    if dest is None and fileobj is None:
        raise ValueError("no destination provided")

    # Check extension
    from_dir = from_dir.rstrip("/")

    # If fileobj is None, dest is not None
    filepath = (
        os.path.abspath(os.path.join(cast(str, dest), filename))
        if fileobj is None
        else None
    )

    ext = check_type(filename, force_extension=force_extension)

    if from_dir_rename is None:
        from_dir_rename = os.path.basename(from_dir)

    if ext == "zip":
        zip_archive = zipfile.ZipFile(
            cast(str, filepath) if fileobj is None else fileobj,
            "w",
            zipfile.ZIP_DEFLATED,
        )
        for root, _, files in os.walk(from_dir):
            relative_root = os.path.relpath(
                os.path.abspath(root), os.path.abspath(from_dir)
            )
            for f in files:
                zip_file_path = os.path.join(from_dir_rename, relative_root, f)
                if no_root_dir:
                    zip_file_path = os.path.join(relative_root, f)
                zip_archive.write(os.path.join(root, f), zip_file_path)
        zip_archive.close()
    else:
        if ext == "tar":
            tar_format = "w"
        elif ext == "tar.gz":
            tar_format = "w:gz"
        elif ext == "tar.bz2":
            tar_format = "w:bz2"
        elif ext == "tar.xz":
            tar_format = "w:xz"
        else:
            assert_never()
        with closing(
            tarfile.open(filepath, fileobj=fileobj, mode=tar_format)
        ) as tar_archive:
            tar_archive.add(name=from_dir, arcname=from_dir_rename, recursive=True)
