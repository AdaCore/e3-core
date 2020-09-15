from __future__ import annotations

from typing import TYPE_CHECKING

import os
import struct
from ctypes import (
    c_wchar_p,
    create_string_buffer,
    create_unicode_buffer,
    pointer,
    sizeof,
)
from ctypes.wintypes import HANDLE

import e3.log
from e3.os.windows.native_api import (
    NT,
    Access,
    FileAttribute,
    FileInfo,
    IOStatusBlock,
    NTException,
    ObjectAttributes,
    OpenOptions,
    Share,
    Status,
    UnicodeString,
)

if TYPE_CHECKING:
    from typing import Any, Callable, Optional, Tuple


logger = e3.log.getLogger("os.windows.fs")


class WithOpenFile:
    def __init__(
        self,
        desired_access: Optional[int] = None,
        shared_access: Optional[int] = None,
        open_options: Optional[int] = None,
    ):
        self.desired_access = desired_access
        self.shared_access = shared_access
        self.open_options = open_options

    def __call__(self, f: Callable) -> Any:
        def wrapper(obj, *args, **kwargs):  # type: ignore
            should_open = not obj.handle
            if should_open:
                obj.open(self.desired_access, self.shared_access, self.open_options)

            try:
                return f(obj, *args, **kwargs)
            finally:
                if should_open:
                    obj.close()

        return wrapper


class NTFile:
    """Class to manipulate Win32 paths.

    :ivar path: the full pathname
    :ivar nt_filename: UnicodeString object representing either the full path
        or the basename of the file (when inititialized using a parent object)
    :ivar handle: handle to the file. It is set to None if no call to open
        has been done
    :ivar io_status: structure returned by most of low level API call
    :ivar basic_info: ObjectAttributes object associated with the file
    """

    def __init__(self, filename: str, parent: Optional[NTFile] = None):
        """Initialize a NTFile object.

        :param filename: path to the file or basename if parent is not None
        :param parent: the parent NTFile object
        """
        self.handle: Optional[HANDLE] = None
        if parent is None:
            self.path = os.path.abspath(filename)
            self.nt_filename = UnicodeString(f"\\??\\{self.path}")
            self.parent_handle = None
        else:
            assert "\\" not in filename and "/" not in filename
            self.path = os.path.join(parent.path, filename)
            self.nt_filename = UnicodeString(str(filename))
            self.parent_handle = parent.handle

        self.io_status = IOStatusBlock()
        self.basic_info = FileInfo.Basic()

        self.attr = ObjectAttributes(self.nt_filename, parent=self.parent_handle)

        self.desired_access = Access.READ_DATA | Access.READ_ATTRS

        # By default don't block access to other processes
        self.shared_access = Share.ALL

        # By default we set BACKUP_INTENT to be able to bypass ACLs in case
        # the user has sufficient rights. It has no effect otherwise
        self.open_options = OpenOptions.BACKUP_INTENT

    def __str__(self) -> str:
        result = [
            "{:<20}: {}".format("path", self.path),
            "{:<20}: {}".format("nt_filename", self.nt_filename),
        ]
        return "\n".join(result)

    def open(
        self,
        desired_access: Optional[int] = None,
        shared_access: Optional[int] = None,
        open_options: Optional[int] = None,
    ) -> None:
        """Open file.

        :param desired_access: desired access
            (see e3.os.windows.native_api.Access)
        :param shared_access: sharing parameters
            (see e3.os.windows.native_api.Shared)
        :param open_options: open options
            (see e3.os.windows.native_api.OpenOptions)
        """
        if desired_access is None:
            desired_access = self.desired_access
        if shared_access is None:
            shared_access = self.shared_access
        if open_options is None:
            open_options = self.open_options

        self.handle = HANDLE()

        open_file: Callable = NT.OpenFile  # type: ignore

        status = open_file(
            pointer(self.handle),
            desired_access,
            pointer(self.attr),
            pointer(self.io_status),
            shared_access,
            open_options,
        )
        if status < 0:
            raise NTException(
                status=status,
                message=f"cannot open file {self.path}",
                origin="NTFile.open",
            )

    def close(self) -> None:
        """Close file.

        If a call has been done to open, close the handle associated
        with the file and reset the handle to None.
        """
        if self.handle:
            NT.Close(self.handle)  # type: ignore
            self.handle = None

    @property
    def volume_path(self) -> str:
        """Retrieve path to the volume containing the file.

        :return: path to a windows volume after junction resolution
        :raise: NTException
        """
        result = create_unicode_buffer(1024)

        get_vol_name: Callable = NT.GetVolumePathName  # type: ignore
        status = get_vol_name(c_wchar_p(self.path), result, 1024)
        if not status:
            raise NTException(
                status=status,
                message=f"cannot find volume for {self.path}",
                origin="NTFile.volume_path",
            )
        return result.value

    @property  # type: ignore
    @WithOpenFile(Access.READ_ATTRS)
    def uid(self) -> int:
        """Retrieve the ID of the file.

        On NTFS system we are sure that this ID is unique on the given volume

        :return: the uid
        :raise: NTException
        """
        result = FileInfo.Internal()

        query_info_file: Callable = NT.QueryInformationFile  # type: ignore

        status = query_info_file(
            self.handle,
            pointer(self.io_status),
            pointer(result),
            sizeof(result),
            FileInfo.Internal.class_id,
        )
        if status < 0:  # defensive code
            # we should already have raised an error here when trying
            # to open the file
            raise NTException(
                status=status, message="cannot find file uid", origin="NTFile.uid"
            )

        return result.index_number

    def read_attributes_internal(self) -> None:
        """Retrieve file basic attributes (internal function).

        The function is used internally to check file basic attributes
        (kind of entry and windows attributes such as readonly). Retrieved
        attributes are stored in basic_info Python attribute. It requires
        less rights than the read_attributes method.
        """
        query_attr_file: Callable = NT.QueryAttributesFile  # type: ignore
        status = query_attr_file(pointer(self.attr), pointer(self.basic_info))
        if status < 0:
            raise NTException(
                status=status,
                message=f"cannot query attributes {self.path}",
                origin="NTFile.read_attributes_internal",
            )

    @WithOpenFile(Access.READ_ATTRS)
    def read_attributes(self) -> FileInfo.Basic:
        """Retrieve file basic information.

        It updates the basic_info attribute including timestamp information

        :raise: NTException
        """
        result = FileInfo.Basic()
        status = NT.QueryInformationFile(  # type: ignore
            self.handle,
            pointer(self.io_status),
            pointer(result),
            sizeof(result),
            FileInfo.Basic.class_id,
        )
        if status < 0:  # defensive code
            # we should already have raised an error here when trying
            # to open the file
            raise NTException(
                status=status,
                message="cannot read attributes",
                origin="NTFile.read_attributes",
            )
        self.basic_info = result
        return result

    @WithOpenFile(Access.WRITE_ATTRS | Access.READ_ATTRS)
    def write_attributes(self) -> None:
        """Update file attributes.

        :raise: NTException
        """
        set_infofile: Callable = NT.SetInformationFile  # type: ignore
        status = set_infofile(
            self.handle,
            pointer(self.io_status),
            pointer(self.basic_info),
            sizeof(self.basic_info),
            FileInfo.Basic.class_id,
        )
        if status < 0:
            raise NTException(
                status=status,
                message=f"cannot write attributes to {self.path}",
                origin="NTFile.write_attributes",
            )
        self.read_attributes()

    @property
    def is_dir(self) -> bool:
        """Check if file is a directory.

        Note that read_attributes methods should be called at least once
        otherwise the function will return False.

        :return: True if the file is a directory, False otherwise
        """
        return self.basic_info.file_attributes.attr & FileAttribute.DIRECTORY > 0

    @property
    def is_readonly(self) -> bool:
        """Check if file is readonly.

        Note that read_attributes methods should be called at least once
        otherwise the function will return False.

        :return: True if readonly, False otherwise
        """
        return self.basic_info.file_attributes.attr & FileAttribute.READONLY > 0

    @property
    def trash_path(self) -> str:
        """Return path in which the file can move safely for deletion.

        On NTFS filesystem we are sure that the path is unique and thus
        that no existing file can exist at that location.

        :return: a path
        """
        return os.path.join(self.volume_path, "tmp", "Trash", str("%016X" % self.uid))

    @WithOpenFile(Access.DELETE)
    def rename(self, filename: str, replace: bool = False) -> None:
        """Move file.

        :param filename: target location
        :param replace: if True replace the target file if it exists
        :raise: NTException
        """
        file_target = f"\\??\\{os.path.abspath(filename)}"
        target = file_target.encode("utf_16_le")
        s = f"?PL{len(target)}s"
        b = create_string_buffer(struct.calcsize(s))
        b.raw = struct.pack(s, replace, 0, len(target), target)

        set_infofile: Callable = NT.SetInformationFile  # type: ignore

        status = set_infofile(
            self.handle,
            pointer(self.io_status),
            b,
            struct.calcsize(s),
            FileInfo.Rename.class_id,
        )
        if status < 0:
            raise NTException(
                status=status,
                message=f"move of {self.path} to {filename} failed",
                origin="NTFile.rename",
            )

    def move_to_trash(self) -> None:
        """Move file to trash location.

        :raise: NTException
        """
        self.rename(self.trash_path, True)

    @WithOpenFile(Access.DELETE, Share.DELETE)
    def dispose(self) -> None:
        """Remove the file (low level).

        The remove is effective on call to close method
        """
        fd = FileInfo.Disposition(1)
        status = NT.SetInformationFile(  # type: ignore
            self.handle,
            pointer(self.io_status),
            pointer(fd),
            sizeof(FileInfo.Disposition),
            FileInfo.Disposition.class_id,
        )
        if status < 0:
            raise NTException(
                status=status, message="cannot dispose", origin="NTFile.dispose"
            )

    @WithOpenFile(
        Access.LIST_DIRECTORY | Access.SYNCHRONIZE,
        None,
        OpenOptions.SYNCHRONOUS_IO_NON_ALERT,
    )
    def iterate_on_dir(self, fun: Callable, default_result: Any = None) -> Any:
        """Iterate on directory.

        :param fun: function called on each entry (. are .. are skipped)
        :param default_result: default return value
        :return: last return value or fun or default_result
        """
        result = default_result
        s_size = struct.calcsize("LLL")
        b_size = 100 * 1024
        b = create_string_buffer(b_size)

        query_dir_file: Callable = NT.QueryDirectoryFile  # type: ignore

        status = query_dir_file(
            self.handle,
            None,
            None,
            None,
            pointer(self.io_status),
            b,
            b_size,
            FileInfo.Names.class_id,
            False,
            None,
            True,
        )
        if status == Status.NO_MORE_FILES:  # defensive code
            # In theory this case should not occurs at it means that the
            # directory does not even have the . and .. entries. In practice
            # it can occurs (probably because of an intermediate state).
            # In that case behave as if the directory is empty
            return result

        if status < 0:
            raise NTException(
                status=status,
                message=f"can't read dir {self.path}",
                origin="NTFile.iterate_on_dir",
            )

        while status >= 0 and status != Status.NO_MORE_FILES:
            pos = 0
            while True:
                off, _, size = struct.unpack_from("LLL", b.raw, pos)
                name = b.raw[pos + s_size : pos + s_size + size].decode("utf-16-le")
                if name != "." and name != "..":
                    result, should_exit = fun(name, self)
                    if should_exit:
                        return result

                if off == 0:
                    break
                pos += off

            status = query_dir_file(
                self.handle,
                None,
                None,
                None,
                pointer(self.io_status),
                b,
                b_size,
                FileInfo.Names.class_id,
                False,
                None,
                False,
            )
        return result

    @property  # type: ignore
    @WithOpenFile(
        Access.LIST_DIRECTORY | Access.SYNCHRONIZE,
        None,
        OpenOptions.SYNCHRONOUS_IO_NON_ALERT,
    )
    def is_dir_empty(self) -> bool:
        """Check if dir is empty.

        :return: True if the directory is empty
        :raise: NTException
        """

        def check_file(filename: str, parent: Optional[NTFile]) -> Tuple[bool, bool]:
            f = NTFile(filename, parent)
            try:
                f.read_attributes_internal()
            except NTException:
                return True, False
            return False, True

        return self.iterate_on_dir(check_file, True)

    def unlink(self) -> None:
        """Remove file safely.

        :raise: NTException
        """
        open_options = self.open_options
        is_in_trash = False

        # First we need to check that file is not mark readonly
        try:
            self.read_attributes_internal()
        except NTException as e:
            if e.status == Status.OBJECT_NAME_NOT_FOUND:
                return
            elif e.status == Status.DELETE_PENDING:
                return
            else:
                raise

        if self.is_readonly:
            # Try to remove the readonly flag
            self.basic_info.file_attributes.attr &= ~FileAttribute.READONLY
            self.write_attributes()

        # set our access modes
        desired_access = Access.DELETE
        shared_access = Share.DELETE
        if self.is_dir:
            desired_access |= Access.LIST_DIRECTORY | Access.SYNCHRONIZE
            open_options |= OpenOptions.SYNCHRONOUS_IO_NON_ALERT

        try_counter = 10
        # Open the file for deletion
        while try_counter > 0:
            try:
                self.open(desired_access, shared_access, open_options)
                break
            except NTException as e:
                if e.status == Status.SHARING_VIOLATION:
                    # File is already open elsewhere for a non delete operation
                    # Try a few times to open it with relaxed share settings
                    shared_access = Share.ALL
                elif e.status == Status.DELETE_PENDING:  # defensive code
                    # file is already pending deletion (just after our call
                    # to read_attributes) so consider the deletion
                    # is done and return
                    return
                else:  # defensive code
                    # We don't know what to do here so just fail
                    raise

            # Wait a few ms before attempting again to open the file
            NT.Sleep(5)  # type: ignore
            try_counter -= 1

        if try_counter == 0:
            raise NTException(
                status=1,
                message=f"cannot open file {self.path} for deletion",
                origin="NTFile.unlink",
            )

        # From there we assume that the file has been opened
        try:
            if shared_access == Share.ALL:
                # The file is also opened elsewhere for a non delete operation
                # In that case we will try to move it to the trash
                # first check that the directory is empty
                if self.is_dir and not self.is_dir_empty:
                    raise NTException(
                        status=1,
                        message=f"directory not empty: {self.path}",
                        origin="NTFile.unlink",
                    )

                self.move_to_trash()
                is_in_trash = True

            # If the file has been moved away then we try to delete it in the
            # trash but it is not necessary to try as hard as the goal is to
            # just keep the trash space used as low as possible.
            if is_in_trash:
                try_counter = 5
            else:
                try_counter = 20

            while try_counter > 0:
                try:
                    self.dispose()
                    break
                except NTException as e:
                    if e.status == Status.DIRECTORY_NOT_EMPTY:
                        # The directory is not empty but that might be because
                        # of remaining files in PENDING_DELETE status. Our
                        # is_dir_empty method return empty if the directory
                        # contains only files pending for deletion
                        if not self.is_dir_empty:
                            raise NTException(
                                status=e.status,
                                message=f"dir {self.path} is not empty",
                                origin="NTFile.unlink",
                            )
                    elif e.status == Status.CANNOT_DELETE:  # defensive code
                        # At this stage we are sure that the file is not
                        # read_only but it seems that we can get this error
                        # when the file has been mapped to memory.
                        if not is_in_trash:
                            try:
                                self.move_to_trash()
                                is_in_trash = True
                                try_counter = min(try_counter, 5)
                            except NTException:
                                pass
                    else:  # defensive code
                        # Unknown error. If the file has been moved away
                        # consider it success. Otherwise reraise exception
                        if is_in_trash:
                            break
                        raise

                NT.Sleep(5)  # type: ignore
                try_counter -= 1

        finally:
            self.close()
