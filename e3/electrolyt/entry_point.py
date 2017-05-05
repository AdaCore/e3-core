from __future__ import absolute_import, division, print_function

from functools import wraps

from enum import Enum


class EntryPointKind(Enum):
    """EntryPoint kind."""

    machine = 0
    ms_preset = 1


def entry_point(db, kind, name, description=None):
    """Entry point decorator.

    Declare an electrolyt entry point (e.g. a machine name, a mailserver
    preset).

    This returns the function with the following new attributes: kind, name,
    description, is_entry_point=True, and executed. Executed is a boolean set
    to False by default and changed to True when the entry point has been
    executed.

    :param db: dictionary where to register the entry point
    :type db: dict
    :param kind: entry point kind (machine name, mailserver preset, ...)
    :type kind: EntryPointKind
    :param name: entry point name (what can be used from electrolyt command
        line)
    :type name: str
    :param description: entry point description
    :type description: str | None
    :raise: AnodError
    """
    def entry_point_dec(
            f, ldb=db, lkind=kind, lname=name, ldescription=description):

        @wraps(f)
        def entry_point_func(*args, **kwargs):
            ldb[lname].executed = True
            return f(*args, **kwargs)

        entry_point_func.is_entry_point = True
        entry_point_func.name = lname
        entry_point_func.kind = lkind
        entry_point_func.description = ldescription
        entry_point_func.executed = False
        ldb[lname] = entry_point_func
        return entry_point_func

    return entry_point_dec
