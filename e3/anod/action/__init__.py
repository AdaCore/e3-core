from e3.anod.spec import Anod


class Action(object):
    """Action object.

    Action objects are used as node in DAG produced by anod scheduler. Only
    child classes are used directly.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, uid, data):
        """Initialize an Action.

        :param uid: an unique identifier
        :type uid: str
        :param data: data associated with the node
        """
        self.uid = uid
        self.data = data


class Root(Action):
    """Root action.

    This action does not correspond to any real activity. It's only used as
    the root of the DAG and can be "executed" only once all the scheduled
    Actions are completed.
    """

    __slots__ = ('uid', 'data')

    def __init__(self):
        """Initialize a root node."""
        self.uid = 'root'
        self.data = 'root'

    def __str__(self):
        return 'root node'


class GetSource(Action):
    """GetSource Action.

    This action means that we need to retrieve a given source package. In the
    anod DAG context it can either have one child node: DownloadSource (read
    access to a store) or provide the choice between DownloadSource or
    CreateSource using a Decision node.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, data):
        Action.__init__(self, 'source_get.%s' % data.name, data)

    def __str__(self):
        return 'get source %s' % self.data.name


class DownloadSource(Action):
    """DownloadSource Action.

    This action means the we need to download from the store a given
    source. DownloadSource is always a leaf of the DAG.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, data):
        Action.__init__(self, 'download.%s' % data.name, data)

    def __str__(self):
        return 'download source %s' % self.data.name


class InstallSource(Action):
    """InstallSource Action.

    This means that a source should be installed. Child action is always
    a GetSource Action.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, uid, data):
        Action.__init__(self, uid, data)

    def __str__(self):
        return 'install source %s' % self.data.name


class CreateSource(Action):
    """CreateSource Action.

    This means that we need to assemble the source package from a repositories
    checkouts. CreateSource has at least one Checkout child node.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, spec, source_name):
        """Initialize CreateSource object.

        :param spec: an Anod instance with primitive set to source
        :type spec: Anod
        :param source_name: name of source package to assemble
        :type source_name: str
        """
        Action.__init__(self,
                        spec.uid + '.' + source_name,
                        data=(spec, source_name))

    def __str__(self):
        return 'create source %s' % self.data[1]


class Checkout(Action):
    """Checkout Action.

    This means that we need to perform the checkout/update of a given
    repository.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, repository):
        Action.__init__(self, 'checkout.%s' % repository, repository)

    def __str__(self):
        return 'checkout %s' % self.data


class AnodAction(Action):
    """AnodAction Action.

    Correspond to an Anod primitive call. Only subclasses should be used.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, data):
        """Initialize an anod Action.

        :param data: an Anod spec instance
        :type data: Anod
        """
        assert isinstance(data, Anod)
        Action.__init__(self, data.uid, data)

    def __str__(self):
        return '%s %s for %s' % (self.data.kind,
                                 self.data.name,
                                 self.data.env.platform)


class Build(AnodAction):
    """Anod build primitive."""

    __slots__ = ('uid', 'data')


class Test(AnodAction):
    """Anod test primitive."""

    __slots__ = ('uid', 'data')


class Install(AnodAction):
    """Anod install primitive."""

    __slots__ = ('uid', 'data')


class DownloadBinary(Action):
    """DownloadBinary Action.

    Download a binary package from the store.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, data):
        """Initialize a DownloadBinary object.

        :param data: Anod instance
        :type data: Anod
        """
        uid = data.uid.split('.')
        uid[-1] = 'download_bin'
        uid = '.'.join(uid)
        Action.__init__(self, uid, data)


class Decision(Action):
    """Decision Action.

    Decision nodes are used when computing the DAG of possible actions.
    A Decision node has two children corresponding to the decision to be
    made during computation of the effective list of actions to perform.
    After scheduling a DAG will not contain any Decision node.
    """

    LEFT = 0
    RIGHT = 1
    BOTH = 2

    def __init__(self, root, left, right, choice=None):
        """Initialize a Decision instance.

        :param root: parent node
        :type root: Action
        :param left: first choice
        :type left: Action
        :param right: second choice
        :type right: Action
        :param choice: expected choice
        :type choice: int
        """
        Action.__init__(self, root.uid + '.decision', None)
        self.choice = choice
        self.left = left.uid
        self.right = right.uid
        self.invalid_choice = None

    def set_invalid_choice(self, which):
        """Mark a given decision as invalid.

        :param which: can be LEFT, RIGHT or BOTH
        :type which: int
        """
        if self.invalid_choice is None:
            self.invalid_choice = which
        elif self.invalid_choice != which:
            self.invalid_choice = Decision.BOTH

    def get_decision(self):
        """Return uid of taken choice.

        :return: None if decision cannot be made or node uid in the
            DAG of the path to follow
        :rtype: None | str
        """
        if self.choice is None or self.choice == Decision.BOTH:
            return None
        else:
            if self.invalid_choice is not None and \
                    (self.invalid_choice == Decision.BOTH or
                     self.invalid_choice == self.choice):
                return None
            elif self.choice == Decision.LEFT:
                return self.left
            else:
                return self.right

    def set_decision(self, which):
        """Make a choice.

        :param which: Decision.LEFT or Decision.RIGHT
        :type which: int
        """
        if self.choice is None:
            self.choice = which
        elif self.choice != which:
            self.choice = Decision.BOTH
