from __future__ import absolute_import, division, print_function

import abc

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

    @property
    def run_method(self):
        return 'do_%s' % self.__class__.__name__.lower()


class Root(Action):
    """Root action.

    This action does not correspond to any real activity. It's only used as
    the root of the DAG and can be "executed" only once all the scheduled
    Actions are completed.
    """

    __slots__ = ('uid', 'data')

    def __init__(self):
        """Initialize a root node."""
        super(Root, self).__init__(uid='root', data='root')

    def __str__(self):
        return 'root node'


class GetSource(Action):
    """GetSource Action.

    This action means that we need to retrieve a given source package. In the
    anod DAG context it can either have one child node: DownloadSource (read
    access to a store) or provide the choice between DownloadSource or
    CreateSource using a Decision node.
    """

    __slots__ = ('uid', 'builder')

    def __init__(self, builder):
        """Object initializer.

        :param builder: A SourceBuilder object for the source we need to get.
        :type builder: e3.anod.package.SourceBuilder
        """
        super(GetSource, self).__init__(uid='source_get.%s' % builder.name,
                                        data=builder)
        self.builder = builder

    def __str__(self):
        return 'get source %s' % self.data.name


class DownloadSource(Action):
    """DownloadSource Action.

    This action means the we need to download from the store a given
    source. DownloadSource is always a leaf of the DAG.
    """

    __slots__ = ('uid', 'builder')

    def __init__(self, builder):
        """Object initializer.

        :param builder: A SourceBuilder object for the source we need
            to download.
        :type builder: e3.anod.package.SourceBuilder
        """
        super(DownloadSource, self).__init__(uid='download.%s' % builder.name,
                                             data=builder)
        self.builder = builder

    def __str__(self):
        return 'download source %s' % self.builder.name


class InstallSource(Action):
    """InstallSource Action.

    This means that a source should be installed. Child action is always
    a GetSource Action.
    """

    __slots__ = ('uid', 'spec', 'source')

    def __init__(self, uid, spec, source):
        """Object initializer.

        :param uid: The job ID for this source's install.
        :type uid: str
        :param spec: The Anod instance of the spec providing those sources.
        :type spec: e3.anod.spec.Anod
        :param source: The source we want to install.
        :type source: e3.anod.package.Source
        """
        super(InstallSource, self).__init__(uid, data=(spec, source))
        self.spec = spec
        self.source = source

    def __str__(self):
        return 'install source %s' % self.data[1].name


class CreateSource(Action):
    """CreateSource Action.

    This means that we need to assemble the source package from a repositories
    checkouts. CreateSource has at least one Checkout child node.
    """

    __slots__ = ('uid', 'anod_instance', 'source_name')

    def __init__(self, anod_instance, source_name):
        """Initialize CreateSource object.

        :param anod_instance: The Anod instance of the spec providing
            the given source.
        :type anod_instance: e3.anod.spec.Anod
        :param source_name: name of source package to assemble
        :type source_name: str
        """
        super(CreateSource, self).__init__(uid='%s.%s' % (anod_instance.uid,
                                                          source_name),
                                           data=(anod_instance, source_name))
        self.anod_instance = anod_instance
        self.source_name = source_name

    def __str__(self):
        return 'create source %s' % self.data[1]


class CreateSources(Action):
    """CreateSources Action.

    This action does not correspond to any real activity. It's only
    used to group all CreateSource action corresponding to the same
    anod spec.
    """

    __slots__ = ('uid', 'anod_instance')

    def __init__(self, anod_instance):
        """Initialize CreateSources object.

        :param anod_instance: the Anod instance of the spec
        :type anod_instance: e3.anod.spec.Anod
        """
        super(CreateSources, self).__init__(
            uid='%s.sources' % anod_instance.uid,
            data=(anod_instance))
        self.anod_instance = anod_instance

    def __str__(self):
        return 'create sources %s' % self.data[1]


class Checkout(Action):
    """Checkout Action.

    This means that we need to perform the checkout/update of a given
    repository.
    """

    __slots__ = ('uid', 'repo_name', 'repo_data')

    def __init__(self, repo_name, repo_data):
        """Initialize a Checkout object.

        :param repo_name: The name of the repository.
        :type repo_name: str
        :param repo_data: A dictionary with the following keys:
            - 'url': The repository URL;
            - 'revision': The revision to checkout;
            - 'vcs': The Version Control System kind (a string).
                At present, only 'git' is supported.
        :type repo_data: dict
        """
        super(Checkout, self).__init__(uid='checkout.%s' % repo_name,
                                       data=(repo_name, repo_data))
        self.repo_name = repo_name
        self.repo_data = repo_data

    def __str__(self):
        return 'checkout %s' % self.data[0]


class AnodAction(Action):
    """AnodAction Action.

    Correspond to an Anod primitive call. Only subclasses should be used.
    """

    __slots__ = ('uid', 'anod_instance')

    def __init__(self, anod_instance):
        """Initialize an anod Action.

        :param anod_instance: an Anod spec instance
        :type anod_instance: e3.anod.spec.Anod
        """
        assert isinstance(anod_instance, Anod)
        super(AnodAction, self).__init__(uid=anod_instance.uid,
                                         data=anod_instance)
        self.anod_instance = anod_instance

    def __str__(self):
        return '%s %s for %s' % (self.data.kind,
                                 self.data.name,
                                 self.data.env.platform)


class Build(AnodAction):
    """Anod build primitive."""

    pass


class Test(AnodAction):
    """Anod test primitive."""

    pass


class Install(AnodAction):
    """Anod install primitive."""

    pass


class DownloadBinary(Action):
    """DownloadBinary Action.

    Download a binary package from the store.
    """

    __slots__ = ('uid', 'data')

    def __init__(self, data):
        """Initialize a DownloadBinary object.

        :param data: Anod instance
        :type data: e3.anod.spec.Anod
        """
        uid = data.uid.split('.')
        uid[-1] = 'download_bin'
        uid = '.'.join(uid)
        super(DownloadBinary, self).__init__(uid=uid, data=data)

    def __str__(self):
        return 'download binary of %s' % \
            self.uid.split('.', 1)[1].rsplit('.', 1)[0]


class UploadComponent(Action):
    """UploadComponent Action.

    Upload a component to the store.
    """

    __slots__ = ('uid', 'data')
    str_prefix = ''

    def __init__(self, data):
        """Initialize an UploadComponent object.

        :param data: Anod instance
        :type data: e3.anod.spec.Anod
        """
        uid = data.uid.split('.')
        uid[-1] = 'upload_bin'
        uid = '.'.join(uid)
        super(UploadComponent, self).__init__(uid=uid, data=data)

    def __str__(self):
        return 'upload %s of %s' % (
            self.str_prefix,
            self.uid.split('.', 1)[1].rsplit('.', 1)[0])


class UploadBinaryComponent(UploadComponent):
    """Upload binary component."""

    str_prefix = 'binary package'


class UploadSourceComponent(UploadComponent):
    """Upload source only component."""

    str_prefix = 'source metadata'


class Decision(Action):
    """Decision Action.

    Decision nodes are used when computing the DAG of possible actions.
    A Decision node has two children corresponding to the decision to be
    made during computation of the effective list of actions to perform.
    After scheduling a DAG will not contain any Decision node.
    """

    __metaclass__ = abc.ABCMeta

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
        super(Decision, self).__init__(uid=root.uid + '.decision', data=None)
        self.initiator = root.uid
        self.choice = choice
        self.expected_choice = None
        self.left = left.uid
        self.left_action = left
        self.right = right.uid
        self.right_action = right
        self.triggers = []
        self.decision_maker = None

    def add_trigger(self, trigger, decision, plan_line):
        """Add a trigger.

        A trigger will be used to set an expected choice depending on the
        presence of a given action in the DAG of scheduled actions

        :param trigger: action that will cause the trigger to be enabled
        :type trigger: Action
        :param decision: expected decision when the trigger action is
            scheduled
        :type decision: int
        :param plan_line: plan line associated with this action
        :type plan_line: str
        """
        self.triggers.append((trigger.uid, decision, plan_line))

    def apply_triggers(self, dag):
        """Apply triggers.

        :param dag: a dag of scheduled actions
        :type dag: e3.collection.dag.DAG
        """
        for uid, decision, _ in self.triggers:
            if uid in dag:
                if self.expected_choice is None:
                    self.expected_choice = decision
                elif self.expected_choice != decision:
                    self.expected_choice = Decision.BOTH

    def get_decision(self):
        """Return uid of taken choice.

        :return: None if decision cannot be made or node uid in the
            DAG of the path to follow
        :rtype: None | str
        """
        if self.choice is None or self.choice == Decision.BOTH:
            return None
        else:
            if self.expected_choice is not None and \
                    self.expected_choice != self.choice:
                return None
            elif self.choice == Decision.LEFT:
                return self.left
            else:
                return self.right

    def get_expected_decision(self):
        """Get expected decision.

        :return: uid of the expected action or None if no specific decision
            is expected.
        :rtype: str | None
        """
        if self.expected_choice == Decision.LEFT:
            return self.left
        elif self.expected_choice == Decision.RIGHT:
            return self.right
        else:
            return None

    def set_decision(self, which, decision_maker):
        """Make a choice.

        :param which: Decision.LEFT or Decision.RIGHT
        :type which: int
        :param decision_maker: record who the decision maker is
        :type decision_maker: None | str
        """
        if self.choice is None:
            self.choice = which
        elif self.choice != which:
            self.choice = Decision.BOTH
        self.decision_maker = decision_maker

    @classmethod
    @abc.abstractmethod
    def description(cls, decision):
        """Return a description of the decision."""
        pass  # all: no cover

    def suggest_plan_fix(self, choice):
        """Suggest a plan line that would fix the conflict.

        :param choice: Decision.LEFT or Decision.RIGHT
        :type choice: int

        :return: a line to add to the plan or None if no fix
             can be proposed
        :rtype: str | None
        """
        return None


class CreateSourceOrDownload(Decision):
    """Decision between creating or downloading a source package."""

    CREATE = Decision.LEFT
    DOWNLOAD = Decision.RIGHT

    def __init__(self, root, left, right):
        """Initialize a CreateSourceOrDownload instance.

        :param root: parent node
        :type root: Action
        :param left: first choice
        :type left: CreateSource
        :param right: second choice
        :type right: DownloadSource
        """
        assert isinstance(left, CreateSource)
        assert isinstance(right, DownloadSource)
        super(CreateSourceOrDownload, self).__init__(root=root,
                                                     left=left,
                                                     right=right)

    @classmethod
    def description(cls, decision):
        return 'CreateSource' if decision == Decision.LEFT \
            else 'DownloadSource'


class BuildOrDownload(Decision):
    """Decision between building or downloading a component."""

    BUILD = Decision.LEFT
    INSTALL = Decision.RIGHT

    def __init__(self, root, left, right):
        """Initialize a BuildOrDownload instance.

        :param root: parent node
        :type root: Install
        :param left: first choice
        :type left: Build
        :param right: second choice
        :type right: DownloadBinary
        """
        assert isinstance(left, Build)
        assert isinstance(right, DownloadBinary)
        assert isinstance(root, Install)
        super(BuildOrDownload, self).__init__(root=root,
                                              left=left,
                                              right=right)

    @classmethod
    def description(cls, decision):
        return 'Build' if decision == Decision.LEFT else 'DownloadBinary'

    def suggest_plan_fix(self, choice):
        action = self.left_action \
            if choice == Decision.LEFT \
            else self.right_action
        spec_instance = action.data

        args = ['"{}"'.format(spec_instance.name)]
        if spec_instance.qualifier:
            args.append('qualifier="{}"'.format(spec_instance.qualifier))
        args.append('build="{}"'.format(spec_instance.env.build.platform))
        if spec_instance.env.host.platform != \
                spec_instance.env.build.platform:
            args.append('host="{}"'.format(
                spec_instance.env.host.platform))
        if spec_instance.env.target.platform != \
                spec_instance.env.host.platform:
            args.append('target="{}"'.format(
                spec_instance.env.target.platform))

        return 'anod_{}({})'.format(spec_instance.kind, ", ".join(args))
