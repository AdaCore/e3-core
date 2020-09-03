from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, Optional


class EntryPoint:
    """Plan Entry point.

    The class represent a valid entry point in an electrolyt plan. It's used
    also to annotate a given entry point with some additional metadata.
    """

    def __init__(
        self,
        db: Dict[str, EntryPoint],
        fun: Callable[[], None],
        kind: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Initialize an entry point.

        :param db: dictionary that tracks the list of entry points
        :param fun: function that implement the entry point
        :param kind: name used in the plan for the entry point decorator
        :param name: name of the entry point. If None then the function
            name is used
        :param description: a description of the entry point
        """
        if name is None:
            self.name = fun.__name__
        else:
            self.name = name
        self.fun = fun
        self.kind = kind
        self.description = description
        self.executed = False
        assert self.name not in db, f"duplicate entry point {self.name}"
        db[self.name] = self

    def execute(self) -> None:
        """Execute an entry point."""
        self.executed = True
        self.fun()


class Machine(EntryPoint):
    """Machine entry point.

    The class is used to declare an entry point which will be the default
    function executed on a given server. It also add some information such
    as the platform and the OS version in order to be able to simulate a plan
    execution.
    """

    def __init__(
        self,
        db: Dict[str, EntryPoint],
        fun: Callable[[], None],
        kind: str,
        platform: str,
        version: str,
        site: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Initialize a Machine entry point.

        :param db: see EntryPoint
        :param fun: see EntryPoint
        :param platform: platform name
        :param version: OS version
        :param site: site indication
        :param name: see EntryPoint
        :param description: see EntryPoint
        """
        super().__init__(db, fun, kind, name, description)
        self.platform = platform
        self.version = version
        self.site = site


def entry_point(
    db: Dict[str, EntryPoint],
    cls: Callable[..., EntryPoint],
    kind: str,
    *args: Any,
    **kwargs: Any,
) -> Callable:
    """Entry point decorator.

    Declare an electrolyt entry point (e.g. a machine name, a mailserver
    preset).

    This returns the function with the following new attributes: kind, name,
    description, is_entry_point=True, and executed. Executed is a boolean set
    to False by default and changed to True when the entry point has been
    executed.

    :param db: dictionary where to register the entry point
    :param cls: class of entry point
    :param kind: entry point kind (machine name, mailserver preset, ...)
    :param args: additional information to store with the entry point
    :param kwargs: additional information to store with the entry point
    """

    def entry_point_dec(  # type: ignore
        f, ldb=db, lcls=cls, lkind=kind, largs=args, lkwargs=kwargs
    ):
        lcls(ldb, f, lkind, *largs, **lkwargs)
        return f

    return entry_point_dec
