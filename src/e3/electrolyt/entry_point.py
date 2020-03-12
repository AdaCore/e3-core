class EntryPoint(object):
    """Plan Entry point.

    The class represent a valid entry point in an electrolyt plan. It's used
    also to annotate a given entry point with some additional metadata.
    """

    def __init__(self, db, fun, kind, name=None, description=None):
        """Initialize an entry point.

        :param db: dictionary that tracks the list of entry points
        :type db: dict[str, EntryPoint]
        :param fun: function that implement the entry point
        :type fun: None -> None
        :param kind: name used in the plan for the entry point decorator
        :type kind: str
        :param name: name of the entry point. If None then the function
            name is used
        :type name: str | None
        :param description: a description of the entry point
        :type description: str | None
        """
        if name is None:
            self.name = fun.__name__
        else:
            self.name = name
        self.fun = fun
        self.kind = kind
        self.description = description
        self.executed = False
        assert self.name not in db, "duplicate entry point %s" % self.name
        db[self.name] = self

    def execute(self):
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
        self, db, fun, kind, platform, version, site=None, name=None, description=None
    ):
        """Initialize a Machine entry point.

        :param db: see EntryPoint
        :param fun: see EntryPoint
        :param platform: platform name
        :type platform: str
        :param version: OS version
        :type version: str
        :param site: site indication
        :type site: str | None
        :param name: see EntryPoint
        :param description: see EntryPoint
        """
        super(Machine, self).__init__(db, fun, kind, name, description)
        self.platform = platform
        self.version = version
        self.site = site


def entry_point(db, cls, kind, *args, **kwargs):
    """Entry point decorator.

    Declare an electrolyt entry point (e.g. a machine name, a mailserver
    preset).

    This returns the function with the following new attributes: kind, name,
    description, is_entry_point=True, and executed. Executed is a boolean set
    to False by default and changed to True when the entry point has been
    executed.

    :param db: dictionary where to register the entry point
    :type db: dict
    :param cls: class of entry point
    :type cls: T
    :param kind: entry point kind (machine name, mailserver preset, ...)
    :type kind: str
    :param args: additional information to store with the entry point
    :param kwargs: additional information to store with the entry point
    """

    def entry_point_dec(f, ldb=db, lcls=cls, lkind=kind, largs=args, lkwargs=kwargs):
        lcls(ldb, f, lkind, *largs, **lkwargs)
        return f

    return entry_point_dec
