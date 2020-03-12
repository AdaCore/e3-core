import ctypes
import sys
import time
from ctypes import (
    POINTER,
    Structure,
    c_wchar_p,
    cast,
    create_unicode_buffer,
    pointer,
    sizeof,
)
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
)
from datetime import datetime

from e3.error import E3Error

NTSTATUS = LONG


class FileAttribute(Structure):
    """List of file attributes constants."""

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

    def __str__(self):
        result = []
        for k in FileAttribute.__dict__:
            if not k.startswith("_") and k.isupper():
                if FileAttribute.__dict__[k] & self.attr > 0:
                    result.append(k)
        return ",".join(result)


class Access(object):
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


class Share(object):
    """Share Access constants."""

    NOTHING = 0x00
    READ = 0x01
    WRITE = 0x02
    DELETE = 0x04
    ALL = 0x07


class OpenOptions(object):
    """File Open options."""

    BACKUP_INTENT = 0x00004000
    SYNCHRONOUS_IO_NON_ALERT = 0x00000020
    DELETE_ON_CLOSE = 0x00001000


class Wait(object):
    """Constants for WaitFor* functions."""

    OBJECT = 0x0000
    ABANDONED = 0x080
    TIMEOUT = 0x0102
    FAILED = 0xFFFFFFFF
    INFINITE = 0xFFFFFFFF


class Status(object):
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


class UnicodeString(Structure):
    """Map UNICODE_STRING structure."""

    _fields_ = [("length", USHORT), ("maximum_length", USHORT), ("buffer", LPWSTR)]

    def __init__(self, value=None, max_length=0):
        strbuf = None
        length = 0
        if value is not None or max_length > 0:
            length = len(value) if value is not None else 0
            max_length = max(length, max_length)
            if value:
                strbuf = create_unicode_buffer(value, max_length)
            else:
                strbuf = create_unicode_buffer(max_length)
        Structure.__init__(self, length * 2, max_length * 2, cast(strbuf, LPWSTR))

    def __len__(self):
        return self.length


class FileTime(Structure):
    """Map FILETIME structure."""

    _fields_ = [("filetime", LARGE_INTEGER)]

    def __init__(self, t):
        timestamp = (t - datetime(1970, 1, 1)).total_seconds()
        timestamp = (int(timestamp) + 11644473600) * 10000000
        Structure.__init__(self, timestamp)

    @property
    def as_datetime(self):
        try:
            return datetime.fromtimestamp(self.filetime // 10000000 - 11644473600)
        except ValueError as err:  # defensive code
            # Add some information to ease debugging
            raise ValueError("filetime '%s' failed with %s" % (self.filetime, err))

    def __str__(self):
        try:
            return str(time.ctime(self.filetime // 10000000 - 11644473600))
        except ValueError:  # defensive code
            return "none"


class FileInfo(object):
    """Declaration of structures returned by QueryInformationFile."""

    class Names(object):
        class_id = 12

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
            ("creation_time", FileTime),
            ("last_access_time", FileTime),
            ("last_write_time", FileTime),
            ("change_time", FileTime),
            ("file_attributes", FileAttribute),
        ]
        class_id = 4

        def __init__(self):
            Structure.__init__(self)
            self.file_attributes = FileAttribute(0)

        def __str__(self):
            result = "creation_time:    %s\n" % self.creation_time
            result += "last_access_time: %s\n" % self.last_access_time
            result += "last_write_time:  %s\n" % self.last_write_time
            result += "change_time:      %s\n" % self.change_time
            result += "file_attributes:  %s" % self.file_attributes
            return result


class ProcessInfo(object):
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

    def __init__(self, name, parent=None):
        """Initialize ObjectAttributes.

        :param name: full path to the file if parent is None else filename
            inside parent directory
        :type name: UnicodeString
        :param parent: handle of the parent directory
        :type parent: HANDLE | None
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
class NT(object):
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

    @classmethod
    def init_api(cls):
        kernel32 = ctypes.windll.kernel32
        ntdll = ctypes.windll.ntdll

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
        cls.WaitForMultipleObjects.argtypes = [DWORD, POINTER(HANDLE), BOOLEAN, DWORD]
        cls.OpenProcess = kernel32.OpenProcess
        cls.OpenProcess.restype = HANDLE
        cls.OpenProcess.argtypes = [DWORD, BOOL, DWORD]


if sys.platform == "win32":
    NT.init_api()


class NTException(E3Error):
    def __init__(self, status, message, origin=None):
        self.status = status
        if self.status < 0:
            self.status += 2 ** 32
        E3Error.__init__(self, message, origin=origin)

    def __str__(self):
        return E3Error.__str__(self) + "(status=%X '%s')" % (
            self.status,
            Status.msgs.get(self.status, "unknown"),
        )
