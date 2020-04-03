from __future__ import annotations

from typing import Callable, List, Optional


def process_exit_code(handle: int) -> Optional[int]:
    """Retrieve process exit code.

    Note that the method used ensure the process stays in a waitable state

    :param handle: process handle
    :return: the exit code if process is finished or None otherwise
    :raise: WindowsError in case the handle is invalid
    """
    from e3.os.windows.native_api import ProcessInfo, NT
    from ctypes import pointer, sizeof

    process_info = ProcessInfo.Basic()
    query_infoprocess: Callable = NT.QueryInformationProcess  # type: ignore
    status = query_infoprocess(
        handle,
        ProcessInfo.Basic.class_id,
        pointer(process_info),
        sizeof(process_info),
        None,
    )
    exit_code = process_info.exit_status

    if status < 0:
        raise OSError("invalid handle")
    elif exit_code == ProcessInfo.STILL_ACTIVE:
        return None
    else:
        return exit_code


def wait_for_objects(
    object_list: List[int], timeout: int = 0, wait_for_all: bool = False
) -> Optional[int]:
    """Wait until list of object are in signaled state.

    :param object_list: a list of handles
    :param timeout: maximum waiting time in seconds. If 0 then maximum waiting
        time is set to infinity
    :param wait_for_all: if True wait for all object to be signaled. If False
        wait for one object to be signaled
    :return: index in the object list of the signaled object or None in case
        of timeout
    :raise: WindowsError
    """
    from e3.os.windows.native_api import NT, Wait
    from ctypes.wintypes import HANDLE

    if timeout == 0:
        timeout = Wait.INFINITE
    else:
        timeout = int(timeout * 1000)

    size = len(object_list)
    handle_array = HANDLE * size
    handles = handle_array(*object_list)

    wait_for_multiples_objects: Callable = NT.WaitForMultipleObjects  # type: ignore

    object_index = wait_for_multiples_objects(size, handles, wait_for_all, timeout)
    if object_index == Wait.TIMEOUT:
        return None
    elif object_index == Wait.FAILED:  # defensive code
        raise OSError("error while waiting for objects")
    elif Wait.ABANDONED <= object_index < Wait.ABANDONED + size:  # defensive code
        return object_index - Wait.ABANDONED
    elif Wait.OBJECT <= object_index < Wait.OBJECT + size:
        return object_index
    else:  # defensive code
        raise OSError("unknown error while waiting for objects")
