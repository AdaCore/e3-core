from __future__ import annotations

import struct
from e3.os.windows.native_api import NT, ObjectInfo
from ctypes.wintypes import HANDLE
from ctypes import create_string_buffer


def object_name(handle: HANDLE) -> str:
    """Given a handle return the windows object name.

    :param handle: object handler
    :return: the windows object name. If no name can be computed the empty
        string is returned.
    """
    # Return result is a UNICODE_STRING structure followed by
    # the buffer of the UNICODE_STRING.
    header_size = struct.calcsize("HHP")
    buf_size = 32768 + header_size
    buf = create_string_buffer(buf_size)
    status = NT.QueryObject(
        handle, ObjectInfo.Name.class_id, buf, buf_size, 0
    )  # type: ignore
    if status < 0:
        return ""

    str_len, _, _ = struct.unpack_from("HHP", buf.raw, 0)
    return buf.raw[header_size : header_size + str_len].decode("utf-16-le")
