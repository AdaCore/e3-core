from __future__ import absolute_import

from ctypes import (Structure, create_unicode_buffer, pointer, cast, c_wchar_p,
                    sizeof, POINTER)
from ctypes.wintypes import (USHORT, LPWSTR, DWORD, LONG, BOOLEAN, INT, BOOL,
                             LARGE_INTEGER, LPVOID, ULONG, HANDLE)
import ctypes
import sys
import time

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

    _fields_ = [('attr', ULONG)]

    def __str__(self):
        result = []
        for k in FileAttribute.__dict__:
            if not k.startswith('_') and k.isupper():
                if FileAttribute.__dict__[k] & self.attr > 0:
                    result.append(k)
        return ",".join(result)


class Access(object):
    """Desired Access constants."""

    LIST_DIR = 0x0001
    READ_ATTRS = 0x0080
    READ_EA = 0x8
    WRITE_ATTRS = 0x0100
    DELETE = 0x010000
    SYNC = 0x100000


class Share(object):
    """Share Access constants."""

    READ = 0x01
    WRITE = 0x02
    DELETE = 0x04
    ALL = 0x07


class OpenOptions(object):
    """File Open options."""

    BACKUP_INTENT = 0x00004000
    SYNCHRONOUS_IO_NON_ALERT = 0x00000020
    DELETE_ON_CLOSE = 0x00001000


class Status(object):
    """Error constants."""

    OBJECT_NAME_NOT_FOUND = 0xC0000034
    OBJECT_PATH_NOT_FOUND = 0xC000003A
    SHARING_VIOLATION = 0xC0000043
    DELETE_PENDING = 0xC0000056

    msgs = {0xC0000034: 'object name not found',
            0xC0000043: 'sharing violation',
            0xC0000056: 'delete pending',
            0xC000003A: 'object path not found'}


class IOStatusBlock(Structure):
    """Map IO_STATUS_BLOCK structure."""

    _fields_ = [('pointer', LPVOID),
                ('information', POINTER(ULONG))]


class UnicodeString(Structure):
    """Map UNICODE_STRING structure."""

    _fields_ = [('length', USHORT),
                ('maximum_length', USHORT),
                ('buffer', LPWSTR)]

    def __init__(self, value=None, max_length=0):
        strbuf = None
        length = 0
        if value is not None or max_length > 0:
            length = len(value)
            max_length = max(length, max_length)
            if value:
                strbuf = create_unicode_buffer(value, max_length)
            else:
                strbuf = create_unicode_buffer(max_length)
        Structure.__init__(self, length * 2, max_length * 2,
                           cast(strbuf, LPWSTR))


class FileTime(Structure):
    """Map FILETIME structure."""

    _fields_ = [('filetime', LARGE_INTEGER)]

    def __str__(self):
        return str(time.ctime(self.filetime / 10000000 - 11644473600))


class FileInfo(object):
    """Declaration of structures returned by QueryInformationFile."""

    class Names(object):
        class_id = 12

    class Disposition(Structure):
        _fields_ = [('delete_file', BOOLEAN)]
        class_id = 13

    class Internal(Structure):
        _fields_ = [('index_number', LARGE_INTEGER)]
        class_id = 6

    class Rename(Structure):
        _fields_ = []
        class_id = 10

    class Basic(Structure):
        _fields_ = [('creation_time', FileTime),
                    ('last_access_time', FileTime),
                    ('last_write_time', FileTime),
                    ('change_time', FileTime),
                    ('file_attributes', FileAttribute)]
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


class ObjectAttributes(Structure):
    """OBJECT_ATTRIBUTES structure."""

    OBJ_CASE_INSENSITIVE = 0x00000040

    _fields_ = [('length', ULONG),
                ('root_directory', HANDLE),
                ('object_name', POINTER(UnicodeString)),
                ('attributes', ULONG),
                ('security_descriptor', LPVOID),
                ('security_quality_of_service', LPVOID)]

    def __init__(self, name, parent=None):
        """Initialize ObjectAttributes.

        :param name: full path to the file if parent is None else filename
            inside parent directory
        :type name: UnicodeString
        :param parent: handle of the parent directory
        :type parent: HANDLE
        """
        Structure.__init__(self,
                           sizeof(ObjectAttributes),
                           parent,
                           pointer(name),
                           self.OBJ_CASE_INSENSITIVE,
                           None,
                           None)


# Declare the Win32 functions return types and signature
class NT(object):

    @classmethod
    def init_api(cls):
        kernel32 = ctypes.windll.kernel32
        ntdll = ctypes.windll.ntdll

        cls.GetVolumePathName = kernel32.GetVolumePathNameW
        cls.GetVolumePathName.restype = BOOL
        cls.GetVolumePathName.argtypes = [c_wchar_p,
                                          c_wchar_p,
                                          DWORD]
        cls.Sleep = kernel32.Sleep
        cls.Sleep.argtypes = [DWORD]

        cls.SetInformationFile = ntdll.NtSetInformationFile
        cls.SetInformationFile.restype = NTSTATUS
        cls.SetInformationFile.argtypes = [HANDLE,
                                           POINTER(IOStatusBlock),
                                           LPVOID,
                                           ULONG,
                                           INT]
        cls.QueryInformationFile = ntdll.NtQueryInformationFile
        cls.QueryInformationFile.restype = NTSTATUS
        cls.QueryInformationFile.argtypes = [HANDLE,
                                             POINTER(IOStatusBlock),
                                             LPVOID,
                                             ULONG,
                                             INT]
        cls.QueryAttributesFile = ntdll.NtQueryAttributesFile
        cls.QueryAttributesFile.restype = NTSTATUS
        cls.QueryAttributesFile.argtypes = [POINTER(ObjectAttributes),
                                            POINTER(FileInfo.Basic)]
        cls.OpenFile = ntdll.NtOpenFile
        cls.OpenFile.restype = NTSTATUS
        cls.OpenFile.argtypes = [POINTER(HANDLE),
                                 DWORD,
                                 POINTER(ObjectAttributes),
                                 POINTER(IOStatusBlock),
                                 ULONG,
                                 ULONG]
        cls.QueryDirectoryFile = ntdll.NtQueryDirectoryFile
        cls.QueryDirectoryFile.restype = NTSTATUS
        cls.QueryDirectoryFile.argtypes = [HANDLE,
                                           HANDLE,
                                           LPVOID,
                                           LPVOID,
                                           POINTER(IOStatusBlock),
                                           LPVOID,
                                           ULONG,
                                           INT,
                                           BOOLEAN,
                                           POINTER(UnicodeString),
                                           BOOLEAN]
        cls.Close = ntdll.NtClose
        cls.Close.argtypes = [HANDLE]


if sys.platform == 'win32':
    NT.init_api()


class NTException(Exception):
    def __init__(self, status, message):
        self.status = status
        if self.status < 0:
            self.status = self.status + 2**32
        Exception.__init__(self, message)

    def __str__(self):
        return "%X (%s): %s" % (self.status, Status.msgs.get(self.status, ''),
                                Exception.__str__(self))
