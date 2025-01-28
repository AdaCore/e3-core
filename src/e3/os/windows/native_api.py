from __future__ import annotations

import ctypes
import sys
import time
from ctypes import POINTER, Structure, c_wchar_p
from ctypes import cast as ctypes_cast
from ctypes import create_unicode_buffer, pointer, sizeof
from ctypes.wintypes import (
    BOOL,
    BOOLEAN,
    DWORD,
    HANDLE,
    INT,
    LARGE_INTEGER,
    LONG,
    LPVOID,
    LPWSTR,
    ULONG,
    USHORT,
    WORD,
)
from datetime import datetime

from e3.error import E3Error

NTSTATUS = LONG


class FileAttribute(Structure):
    """list of file attributes constants."""

    READONLY = 0x01
    HIDDEN = 0x02
    SYSTEM = 0x04
    DIRECTORY = 0x10
    ARCHIVE = 0x20
    DEVICE = 0x40
    NORMAL = 0x80
    TEMPORARY = 0x100
    SPARSE_FILE = 0x200
    REPARSE_POINT = 0x400
    COMPRESSED = 0x800
    OFFLINE = 0x1000
    NOT_CONTENT_INDEXED = 0x2000
    ENCRYPTED = 0x4000
    INTEGRITY_STREAM = 0x8000
    VIRTUAL = 0x10000
    NO_SCRUB_DATA = 0x20000

    _fields_ = [("attr", ULONG)]

    def __str__(self) -> str:
        result = []
        for k in FileAttribute.__dict__:
            if not k.startswith("_") and k.isupper():
                if FileAttribute.__dict__[k] & self.attr > 0:
                    result.append(k)
        return ",".join(result)


class IOReparseTag:
    """Reparse Point Tag constants.

    This is important to note that symbolic links on Windows are always implemented
    using reparse points. Nevertheless a reparse point is a more general concept not
    always associated with the concept of symbolic links. In the present code we are
    only interested in checking whether a reparse point is a symbolic link or not.

    Currenly Windows supports two kinds of symbolic links. One for Win32 apps (SYMLINK)
    and one for WSL subsystem (WSL_SYMLINK). Note that Cygwin now uses the second one
    to implement symbolic links. Note that WSL symbolic links are not handled correctly
    by the Python runtime (for example os.path.islink will return False).
    """

    SYMLINK = 0xA000000C
    WSL_SYMLINK = 0xA000001D


class Access:
    """Desired Access constants."""

    LIST_DIRECTORY = 0x0001
    READ_DATA = 0x0001
    ADD_FILE = 0x0002
    WRITE_DATA = 0x0002
    ADD_SUBDIR = 0x0004
    APPEND_DATA = 0x0004
    READ_EA = 0x0008
    WRITE_EA = 0x0010
    EXECUTE = 0x0020
    TRAVERSE = 0x0020
    DELETE_CHILD = 0x0040
    READ_ATTRS = 0x0080
    WRITE_ATTRS = 0x0100
    DELETE = 0x010000
    SYNCHRONIZE = 0x100000
    PROCESS_QUERY_INFORMATION = 0x0400


class Share:
    """Share Access constants."""

    NOTHING = 0x00
    READ = 0x01
    WRITE = 0x02
    DELETE = 0x04
    ALL = 0x07


class OpenOptions:
    """File Open options."""

    BACKUP_INTENT = 0x00004000
    SYNCHRONOUS_IO_NON_ALERT = 0x00000020
    DELETE_ON_CLOSE = 0x00001000
    OPEN_REPARSE_POINT = 0x00200000


class Wait:
    """Constants for WaitFor* functions."""

    OBJECT = 0x0000
    ABANDONED = 0x080
    TIMEOUT = 0x0102
    FAILED = 0xFFFFFFFF
    INFINITE = 0xFFFFFFFF


class Status:
    """Error constants."""

    ACCESS_DENIED = 0xC0000022
    OBJECT_NAME_NOT_FOUND = 0xC0000034
    OBJECT_PATH_NOT_FOUND = 0xC000003A
    SHARING_VIOLATION = 0xC0000043
    DELETE_PENDING = 0xC0000056
    DIRECTORY_NOT_EMPTY = 0xC0000101
    CANNOT_DELETE = 0xC0000121
    NO_MORE_FILES = 0x80000006

    msgs = {
        0xC0000022: "access denied",
        0xC0000034: "object name not found",
        0xC0000043: "sharing violation",
        0xC0000056: "delete pending",
        0xC000003A: "object path not found",
        0xC0000101: "directory is not empty",
        0xC0000121: "cannot delete",
    }


class IOStatusBlock(Structure):
    """Map IO_STATUS_BLOCK structure."""

    _fields_ = [("status", NTSTATUS), ("information", POINTER(ULONG))]


class ReparseGUIDDataBuffer(Structure):
    _fields_ = [
        ("tag", DWORD),
        ("length", WORD),
        ("reserved", WORD),
        ("guid", DWORD),
        ("data", ctypes.c_char * (16 * 1024)),
    ]


class UnicodeString(Structure):
    """Map UNICODE_STRING structure."""

    _fields_ = [("length", USHORT), ("maximum_length", USHORT), ("buffer", LPWSTR)]

    def __init__(self, value: str | None = None, max_length: int = 0):
        strbuf = None
        length = 0
        if value is not None or max_length > 0:
            length = len(value) if value is not None else 0
            max_length = max(length, max_length)
            if value:
                strbuf = create_unicode_buffer(value, max_length)
            else:
                strbuf = create_unicode_buffer(max_length)

        ctypes_strbuf = ctypes_cast(strbuf, LPWSTR)  # type: ignore

        Structure.__init__(self, length * 2, max_length * 2, ctypes_strbuf)

    def __len__(self) -> int:
        return self.length


# Offset in seconds between Windows and Linux epoch. Windows use January 1st 1601
# whereas Posix systems are using January 1st 1970.
W32_EPOCH_OFFSET = 11_644_473_600


class FileTime(Structure):
    """Map FILETIME structure."""

    # Note: in a previous implementation that structure was directly mapped to
    # LARGE_INTEGER Doing that is wrong as it force an implicit 8 byte alignment.
    # Some structures do not respect that alignment (See FindData for example).
    _fields_ = [("filetime_low", DWORD), ("filetime_high", DWORD)]

    def __init__(self, t: datetime) -> None:
        # Transform date to Windows timestamp
        timestamp = (t - datetime(1970, 1, 1)).total_seconds()

        # Windows use hundreds of ns as unit
        timestamp = (int(timestamp) + W32_EPOCH_OFFSET) * 10_000_000

        Structure.__init__(self, timestamp % 2**32, timestamp // 2**32)

    @property
    def filetime(self) -> int:
        return self.filetime_low + self.filetime_high * 2**32

    @property
    def as_datetime(self) -> datetime:
        try:
            return datetime.fromtimestamp(
                self.filetime // 10_000_000 - W32_EPOCH_OFFSET
            )
        except ValueError as err:  # defensive code
            # Add some information to ease debugging
            raise ValueError(f"filetime '{self.filetime}' failed with {err}") from err

    def __str__(self) -> str:
        try:
            return str(time.ctime(self.filetime // 10_000_000 - W32_EPOCH_OFFSET))
        except ValueError:  # defensive code
            return "none"


class LargeFileTime(Structure):
    """Map filetime implemented using LARGE_INTEGER."""

    # Contrary to WIN32 API, Native API use LARGE_INTEGER instead of a tuple
    # of DWORD. This means that there is an implicit alignment constraint of
    # 8 bytes. As consequence even if similar, this should not be merged with
    # FileTime.
    _fields_ = [("filetime", LARGE_INTEGER)]

    def __init__(self, t: datetime) -> None:
        # Transform date to Windows timestamp
        timestamp = (t - datetime(1970, 1, 1)).total_seconds()

        # Windows use hundreds of ns as unit
        timestamp = (int(timestamp) + W32_EPOCH_OFFSET) * 10_000_000
        Structure.__init__(self, timestamp)

    @property
    def as_datetime(self) -> datetime:
        try:
            return datetime.fromtimestamp(
                self.filetime // 10_000_000 - W32_EPOCH_OFFSET
            )
        except ValueError as err:  # defensive code
            # Add some information to ease debugging
            raise ValueError(f"filetime '{self.filetime}' failed with {err}") from err

    def __str__(self) -> str:
        try:
            return str(time.ctime(self.filetime // 10_000_000 - W32_EPOCH_OFFSET))
        except ValueError:  # defensive code
            return "none"


class FindData(Structure):
    _fields_ = [
        ("file_attributes", FileAttribute),
        ("creation_time", FileTime),
        ("last_access_time", FileTime),
        ("last_write_time", FileTime),
        ("file_size0", DWORD),
        ("file_size1", DWORD),
        # When the file is a reparse point, reserved0 field contains the reparse point
        # tag (i.e: the reparse point kind).
        ("reserved0", DWORD),
        ("reserved1", DWORD),
        ("filename", ctypes.c_wchar * 260),
        ("dos_filename", ctypes.c_wchar * 14),
        ("unused0", DWORD),
        ("unused1", DWORD),
        ("unused2", WORD),
    ]


class FileInfo:
    """Declaration of structures returned by QueryInformationFile."""

    class Names:
        class_id = 12

    class ReparsePoint(Structure):
        _fields_ = [("file_reference", LARGE_INTEGER), ("tag", ULONG)]
        class_id = 33

    class Disposition(Structure):
        _fields_ = [("delete_file", BOOLEAN)]
        class_id = 13

    class Internal(Structure):
        _fields_ = [("index_number", LARGE_INTEGER)]
        class_id = 6

    class Rename(Structure):
        _fields_ = []
        class_id = 10

    class Basic(Structure):
        _fields_ = [
            ("creation_time", LargeFileTime),
            ("last_access_time", LargeFileTime),
            ("last_write_time", LargeFileTime),
            ("change_time", LargeFileTime),
            ("file_attributes", FileAttribute),
        ]
        class_id = 4

        def __init__(self) -> None:
            Structure.__init__(self)
            self.file_attributes = FileAttribute(0)

        def __str__(self) -> str:
            result = f"creation_time:    {self.creation_time}\n"
            result += f"last_access_time: {self.last_access_time}\n"
            result += f"last_write_time:  {self.last_write_time}\n"
            result += f"change_time:      {self.change_time}\n"
            result += f"file_attributes:  {self.file_attributes}"
            return result


class ObjectInfo:
    """Declaration of structures returned by QueryObjectInformation."""

    class Name(Structure):
        _fields_ = []
        class_id = 1


class ProcessInfo:
    """Declaration of structure returned by QueryInformationProcess."""

    class Basic(Structure):
        class_id = 0

        _fields_ = [
            ("exit_status", NTSTATUS),
            ("peb", LPVOID),
            ("affinity_mask", LPVOID),
            ("base_priority", LONG),
            ("pid", LPVOID),
            ("ppid", LPVOID),
        ]

    STILL_ACTIVE = 259


class ObjectAttributes(Structure):
    """OBJECT_ATTRIBUTES structure."""

    OBJ_CASE_INSENSITIVE = 0x00000040

    _fields_ = [
        ("length", ULONG),
        ("root_directory", HANDLE),
        ("object_name", POINTER(UnicodeString)),
        ("attributes", ULONG),
        ("security_descriptor", LPVOID),
        ("security_quality_of_service", LPVOID),
    ]

    def __init__(self, name: UnicodeString, parent: HANDLE | None = None):
        """Initialize ObjectAttributes.

        :param name: full path to the file if parent is None else filename
            inside parent directory
        :param parent: handle of the parent directory
        """
        Structure.__init__(
            self,
            sizeof(ObjectAttributes),
            parent,
            pointer(name),
            self.OBJ_CASE_INSENSITIVE,
            None,
            None,
        )


# Declare the Win32 functions return types and signature
class NT:
    FindFirstFile = None
    FindClose = None
    FsControlFile = None
    Sleep = None
    GetVolumePathName = None
    SetInformationFile = None
    QueryInformationFile = None
    QueryAttributesFile = None
    OpenFile = None
    QueryDirectoryFile = None
    Close = None
    QueryInformationProcess = None
    WaitForMultipleObjects = None
    OpenProcess = None
    QueryObject = None

    @classmethod
    def init_api(cls) -> None:
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            ntdll = ctypes.windll.ntdll

            cls.FsControlFile = ntdll.NtFsControlFile
            cls.FsControlFile.restype = NTSTATUS
            cls.FsControlFile.argtypes = [
                HANDLE,
                HANDLE,
                LPVOID,
                LPVOID,
                POINTER(IOStatusBlock),
                ULONG,
                LPVOID,
                ULONG,
                POINTER(ReparseGUIDDataBuffer),
                ULONG,
            ]

            cls.FindFirstFile = kernel32.FindFirstFileW
            cls.FindFirstFile.restype = HANDLE
            cls.FindFirstFile.argtypes = [c_wchar_p, POINTER(FindData)]

            cls.FindClose = kernel32.FindClose
            cls.FindClose.restype = BOOL
            cls.FindClose.argtypes = [HANDLE]

            cls.GetVolumePathName = kernel32.GetVolumePathNameW
            cls.GetVolumePathName.restype = BOOL
            cls.GetVolumePathName.argtypes = [c_wchar_p, c_wchar_p, DWORD]
            cls.Sleep = kernel32.Sleep
            cls.Sleep.argtypes = [DWORD]

            cls.SetInformationFile = ntdll.NtSetInformationFile
            cls.SetInformationFile.restype = NTSTATUS
            cls.SetInformationFile.argtypes = [
                HANDLE,
                POINTER(IOStatusBlock),
                LPVOID,
                ULONG,
                INT,
            ]
            cls.QueryInformationFile = ntdll.NtQueryInformationFile
            cls.QueryInformationFile.restype = NTSTATUS
            cls.QueryInformationFile.argtypes = [
                HANDLE,
                POINTER(IOStatusBlock),
                LPVOID,
                ULONG,
                INT,
            ]
            cls.QueryObject = ntdll.NtQueryObject
            cls.QueryObject.restype = NTSTATUS
            cls.QueryObject.argtypes = [HANDLE, INT, LPVOID, ULONG, LPVOID]

            cls.QueryAttributesFile = ntdll.NtQueryAttributesFile
            cls.QueryAttributesFile.restype = NTSTATUS
            cls.QueryAttributesFile.argtypes = [
                POINTER(ObjectAttributes),
                POINTER(FileInfo.Basic),
            ]
            cls.OpenFile = ntdll.NtOpenFile
            cls.OpenFile.restype = NTSTATUS
            cls.OpenFile.argtypes = [
                POINTER(HANDLE),
                DWORD,
                POINTER(ObjectAttributes),
                POINTER(IOStatusBlock),
                ULONG,
                ULONG,
            ]
            cls.QueryDirectoryFile = ntdll.NtQueryDirectoryFile
            cls.QueryDirectoryFile.restype = NTSTATUS
            cls.QueryDirectoryFile.argtypes = [
                HANDLE,
                HANDLE,
                LPVOID,
                LPVOID,
                POINTER(IOStatusBlock),
                LPVOID,
                ULONG,
                INT,
                BOOLEAN,
                POINTER(UnicodeString),
                BOOLEAN,
            ]
            cls.Close = ntdll.NtClose
            cls.Close.argtypes = [HANDLE]
            cls.QueryInformationProcess = ntdll.NtQueryInformationProcess
            cls.QueryInformationProcess.restype = NTSTATUS
            cls.QueryInformationProcess.argtypes = [
                HANDLE,
                INT,
                POINTER(ProcessInfo.Basic),
                ULONG,
                LPVOID,
            ]
            cls.WaitForMultipleObjects = kernel32.WaitForMultipleObjects
            cls.WaitForMultipleObjects.restype = DWORD
            cls.WaitForMultipleObjects.argtypes = [
                DWORD,
                POINTER(HANDLE),
                BOOLEAN,
                DWORD,
            ]
            cls.OpenProcess = kernel32.OpenProcess
            cls.OpenProcess.restype = HANDLE
            cls.OpenProcess.argtypes = [DWORD, BOOL, DWORD]


if sys.platform == "win32":
    NT.init_api()


class NTException(E3Error):
    def __init__(self, status: int, message: str, origin: str | None = None):
        self.status = status
        if self.status < 0:
            self.status += 2**32
        E3Error.__init__(self, message, origin=origin)

    def __str__(self):
        return E3Error.__str__(self) + "(status={:X} '{}')".format(
            self.status,
            Status.msgs.get(self.status, "unknown"),
        )
