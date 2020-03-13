import abc

from e3.anod.spec import Anod


class Action(object):
    """Action object.

    Action objects are used as node in DAG produced by anod scheduler. Only
    child classes are used directly.
    """

    __slots__ = ("uid", "data")

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
        return "do_%s" % self.__class__.__name__.lower()


class Root(Action):
    """Root action.

    This action does not correspond to any real activity. It's only used as
    the root of the DAG and can be "executed" only once all the scheduled
    Actions are completed.
    """

    __slots__ = ("uid", "data")

    def __init__(self):
        """Initialize a root node."""
        super(Root, self).__init__(uid="root", data="root")

    def __str__(self):
        return "root node"


class GetSource(Action):
    """GetSource Action.

    This action means that we need to retrieve a given source package. In the
    anod DAG context it can either have one child node: DownloadSource (read
    access to a store) or provide the choice between DownloadSource or
    CreateSource using a Decision node.
    """

    __slots__ = ("uid", "builder")

    def __init__(self, builder):
        """Object initializer.

        :param builder: A SourceBuilder object for the source we need to get.
        :type builder: e3.anod.package.SourceBuilder
        """
        super(GetSource, self).__init__(
            uid="source_get.%s" % builder.name, data=builder
        )
        self.builder = builder

    def __str__(self):
        return "get source %s" % self.data.name


class Download(Action):
    """General root class for all download actions."""

    pass


class DownloadSource(Download):
    """DownloadSource Action.

    This action means the we need to download from the store a given
    source. DownloadSource is always a leaf of the DAG.
    """

    __slots__ = ("uid", "builder")

    def __init__(self, builder):
        """Object initializer.

        :param builder: A SourceBuilder object for the source we need
            to download.
        :type builder: e3.anod.package.SourceBuilder
        """
        super(DownloadSource, self).__init__(
            uid="download.%s" % builder.name, data=builder
        )
        self.builder = builder

    def __str__(self):
        return "download source %s" % self.builder.name


class InstallSource(Action):
    """InstallSource Action.

    This means that a source should be installed. Child action is always
    a GetSource Action.
    """

    __slots__ = ("uid", "spec", "source")

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
        return "install source %s" % self.data[1].name


class CreateSource(Action):
    """CreateSource Action.

    This means that we need to assemble the source package from a repositories
    checkouts. CreateSource has at least one Checkout child node.
    """

    __slots__ = ("uid", "anod_instance", "source_name")

    def __init__(self, anod_instance, source_name):
        """Initialize CreateSource object.

        :param anod_instance: The Anod instance of the spec providing
            the given source.
        :type anod_instance: e3.anod.spec.Anod
        :param source_name: name of source package to assemble
        :type source_name: str
        """
        super(CreateSource, self).__init__(
            uid="%s.%s" % (anod_instance.uid, source_name),
            data=(anod_instance, source_name),
        )
        self.anod_instance = anod_instance
        self.source_name = source_name

    def __str__(self):
        return "create source %s" % self.data[1]


class CreateSources(Action):
    """CreateSources Action.

    This action does not correspond to any real activity. It's only
    used to group all CreateSource action corresponding to the same
    anod spec.
    """

    __slots__ = ("uid", "anod_instance")

    def __init__(self, anod_instance):
        """Initialize CreateSources object.

        :param anod_instance: the Anod instance of the spec
        :type anod_instance: e3.anod.spec.Anod
        """
        super(CreateSources, self).__init__(
            uid="%s.sources" % anod_instance.uid, data=(anod_instance)
        )
        self.anod_instance = anod_instance

    def __str__(self):
        return "create all sources for %s.anod" % self.anod_instance.name


class Checkout(Action):
    """Checkout Action.

    This means that we need to perform the checkout/update of a given
    repository.
    """

    __slots__ = ("uid", "repo_name", "repo_data")

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
        super(Checkout, self).__init__(
            uid="checkout.%s" % repo_name, data=(repo_name, repo_data)
        )
        self.repo_name = repo_name
        self.repo_data = repo_data

    def __str__(self):
        return "checkout %s" % self.data[0]


class AnodAction(Action):
    """AnodAction Action.

    Correspond to an Anod primitive call. Only subclasses should be used.
    """

    __slots__ = ("uid", "anod_instance")

    def __init__(self, anod_instance):
        """Initialize an anod Action.

        :param anod_instance: an Anod spec instance
        :type anod_instance: e3.anod.spec.Anod
        """
        assert isinstance(anod_instance, Anod)
        super(AnodAction, self).__init__(uid=anod_instance.uid, data=anod_instance)
        self.anod_instance = anod_instance

    def __str__(self):
        result = "%s %s for %s" % (
            self.data.kind,
            self.data.name,
            self.data.env.platform,
        )
        if self.data.qualifier:
            result += " (qualifier=%s)" % self.data.qualifier
        return result


class Build(AnodAction):
    """Anod build primitive."""

    pass


class Test(AnodAction):
    """Anod test primitive."""

    pass


class Install(AnodAction):
    """Anod install primitive."""

    pass


class DownloadBinary(Download):
    """DownloadBinary Action.

    Download a binary package from the store.
    """

    __slots__ = ("uid", "data")

    def __init__(self, data):
        """Initialize a DownloadBinary object.

        :param data: Anod instance
        :type data: e3.anod.spec.Anod
        """
        uid = data.uid.split(".")
        uid[-1] = "download_bin"
        uid = ".".join(uid)
        super(DownloadBinary, self).__init__(uid=uid, data=data)

    def __str__(self):
        return "download binary of %s" % self.uid.split(".", 1)[1].rsplit(".", 1)[0]


class Upload(Action):
    """General root class for all upload actions."""

    pass


class UploadComponent(Upload):
    """UploadComponent Action.

    Upload a component to the store.
    """

    __slots__ = ("uid", "data", "anod_instance")
    str_prefix = ""

    def __init__(self, data):
        """Initialize an UploadComponent object.

        :param data: Anod instance
        :type data: e3.anod.spec.Anod
        """
        uid = data.uid.split(".")
        uid[-1] = "upload_bin"
        uid = ".".join(uid)
        super(UploadComponent, self).__init__(uid=uid, data=data)
        self.anod_instance = data

    def __str__(self):
        return "upload %s of %s" % (
            self.str_prefix,
            self.uid.split(".", 1)[1].rsplit(".", 1)[0],
        )


class UploadBinaryComponent(UploadComponent):
    """Upload binary component."""

    str_prefix = "binary package"


class UploadSourceComponent(UploadComponent):
    """Upload source only component."""

    str_prefix = "source metadata"


class UploadSource(Upload):
    """Upload a source package."""

    __slots__ = ("uid", "anod_instance", "source_name")

    def __init__(self, anod_instance, source_name):
        """Initialize UploadSource object.

        :param anod_instance: The Anod instance of the spec providing
            the given source.
        :type anod_instance: e3.anod.spec.Anod
        :param source_name: name of source package to assemble
        :type source_name: str
        """
        uid = anod_instance.uid.split(".")
        uid[-1] = "upload_src"
        uid.append(source_name)
        uid = ".".join(uid)
        super(UploadSource, self).__init__(uid=uid, data=(anod_instance, source_name))
        self.anod_instance = anod_instance
        self.source_name = source_name

    def __str__(self):
        """Return string representation."""
        return "upload source %s" % self.source_name


class Decision(Action, metaclass=abc.ABCMeta):
    """Decision Action.

    Decision nodes correspond to Action nodes where the end result
    can be obtained using multiple methods. For instance, sources
    can be obtained either by downloading them from the store, but
    also by getting them from repositories.  Each child of Decision nodes
    represents one way to obtain the desired end result (a "choice").

    The current implementation only supports 2 choices, called
    "left" and "right".

    The DAG we first create when reading the plan includes these Decision
    nodes. Then, as part of scheduling the plan, we create a new DAG where
    all Decision nodes are removed, and only one child of each Decision
    is chosen by the scheduler, then taking the place of its Decision
    node in the DAG. Therefore, once scheduling of the DAG is complete,
    there should no longer be any Decision node left.

    It important to know that this class does not actually decide
    which choice to make. It just records some information about
    the plan, and the associated specs. It then uses that information
    to determine if a choice has actually been made, be it implicitly
    or explicitly.

    :ivar initiator: The UID of the parent node of the decision.
    :vartype initiator: str
    :ivar left_action: The first possible choice for our decision.
    :vartype left_action: Action.
    :ivar right_action: The second possible choice for our decision.
    :vartype right_action: Action.
    :ivar choice: If not None, the choice made by the plan itself.
        It can be Decision.LEFT, meaning that the plan contains
        an entry to perform the self.left_action; If set to
        Decision.RIGHT, it means the plan contains an entry to
        perform the self.right_action; and if set to BOTH, it means
        the plan contains entries to perform both self.left_action
        and self.right_action (which may or may not be an issue).
    :vartype choice: Decision.LEFT | Decision.RIGHT | Decision.BOTH
    :ivar expected_choice: If not None, the choice implicitly made
        by the way the specs involved in the decision are written.
        In practice, this attribute records the constraints we have
        in terms of the choices in the plan which are valid.
    :ivar triggers: A list of actions that, if present in a DAG
        being created while scheduling the plan (from which this
        Decision originates), causes a specific choice to be expected
        for this decision.  Each element of this list consists of a tuple
        with the uid of the Action triggering the choice, the expected
        choice, and a plan_line (if the action comes from the plan,
        otherwise None).
    :vartype triggers: list[(str, LEFT | RIGHT, str | None)]
    :ivar decision_maker: If not None, the plan_line where an entry
        in the plan is performing an action corresponding to one of
        our choices.
    :ivar: str
    """

    LEFT = 0
    RIGHT = 1
    BOTH = 2

    def __init__(self, root, left, right, choice=None):
        """Initialize a Decision instance.

        :param root: parent node
        :type root: Action
        :param left: Same as the left_action attribute.
        :type left: Action
        :param right: Same as the right_action attribute.
        :type right: Action
        :param choice: Same as the attribute.
        :type choice: int | None
        """
        super(Decision, self).__init__(uid=root.uid + ".decision", data=None)
        self.initiator = root.uid
        self.choice = choice
        self.expected_choice = None
        self.left_action = left
        self.right_action = right
        self.triggers = []
        self.decision_maker = None

    @property
    def left(self):
        """return self.left_action.uid (this is a convenience property)."""
        return self.left_action.uid

    @property
    def right(self):
        """return self.right_action.uid (this is a convenience property)."""
        return self.right_action.uid

    def add_trigger(self, trigger, decision, plan_line):
        """Add a trigger to self.triggers.

        See the description of the "triggers" attribute for more
        information as to what these triggers are used for.

        :param trigger: The action which, when scheduled, causes
            the given decision (which is actually more aptly
            described as a choice) to be recorded as the expected
            choice for our Decision.
        :type trigger: Action
        :param decision: The expected choice when the trigger Action is
            scheduled.
        :type decision: int
        :param plan_line: plan line associated with this action
        :type plan_line: str
        """
        self.triggers.append((trigger.uid, decision, plan_line))

    def apply_triggers(self, dag):
        """Apply triggers to the given dag.

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
        """Return uid of the choice made by the plan, or None.

        This function returns the choice made by the plan, if any.
        This means that if the plan doesn't include an action
        that implements any of the choices, we return None.
        Similarly, if the plan has actions implementing more than
        one of the choices, the plan hasn't made any decision
        because the decision is ambiguous.

        And finally, if the plan made a choice, but that choice
        contradicts this decision's expected_choice, then the decision
        is incorrect, and we also return None in that case.

        :return: None if the decision cannot be made; otherwise,
            return uid of the choice that was made.
        :rtype: None | str
        """
        if self.choice is None or self.choice == Decision.BOTH:
            return None
        else:
            if self.expected_choice is not None and self.expected_choice != self.choice:
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
        """Record a choice made by an action in a plan.

        This method should be caused when an entry in our plan
        performs an action corresponding to one of the choices
        for our decision. This method records which of the choices
        that action performs.

        :param which: Decision.LEFT or Decision.RIGHT
        :type which: int
        :param decision_maker: Record who the decision maker is.
            This is typically the plan line of the action performing
            the choice being recorded.
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
        """Return a description of the decision (actually a choice).

        :param decision: The decision (actually a choice).
        :type decision: int
        :return: A description of the given parameter (named "decision",
            but actually a choice).
        :rtype: str
        """
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
        super(CreateSourceOrDownload, self).__init__(root=root, left=left, right=right)

    @classmethod
    def description(cls, decision):
        return "CreateSource" if decision == Decision.LEFT else "DownloadSource"


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
        super(BuildOrDownload, self).__init__(root=root, left=left, right=right)

    @classmethod
    def description(cls, decision):
        return "Build" if decision == Decision.LEFT else "DownloadBinary"

    def suggest_plan_fix(self, choice):
        action = self.left_action if choice == Decision.LEFT else self.right_action
        spec_instance = action.data

        args = ['"{}"'.format(spec_instance.name)]
        if spec_instance.qualifier:
            args.append('qualifier="{}"'.format(spec_instance.qualifier))
        args.append('build="{}"'.format(spec_instance.env.build.platform))
        if spec_instance.env.host.platform != spec_instance.env.build.platform:
            args.append('host="{}"'.format(spec_instance.env.host.platform))
        if spec_instance.env.target.platform != spec_instance.env.host.platform:
            args.append('target="{}"'.format(spec_instance.env.target.platform))

        return "anod_{}({})".format(spec_instance.kind, ", ".join(args))
