from __future__ import absolute_import, division, print_function

from e3.anod.action import (Build, BuildOrInstall, Checkout, CreateSource,
                            CreateSourceOrDownload, Decision, DownloadBinary,
                            DownloadSource, GetSource, Install,
                            InstallSource, Root, Test, UploadBinaryComponent,
                            UploadComponent, UploadSourceComponent)
from e3.anod.deps import Dependency
from e3.anod.error import AnodError
from e3.anod.package import UnmanagedSourceBuilder
from e3.anod.spec import has_primitive
from e3.collection.dag import DAG
from e3.env import BaseEnv
from e3.error import E3Error


class SchedulingError(E3Error):
    """Exception raised by scheduling algorithm."""

    def __init__(self, message, origin=None, uid=None, initiators=None):
        """Scheduling error initialization.

        :param message: the exception message
        :type message: str
        :param origin: the name of the function, class, or module having raised
            the exception
        :type origin: str
        :param uid: uid of action that cause the error
        :type uid: str
        :param initiators: list of uids involved in the failure
        :type initiators: list[str] | None
        """
        super(SchedulingError, self).__init__(message, origin)
        self.uid = uid
        self.initiators = initiators


class AnodContext(object):
    """Anod context.

    :ivar repo: an anod spec repository
    :ivar tree: a DAG containing the list of possible actions
    :ivar root: root node of the DAG
    :ivar cache: cache of anod instances
    :ivar sources: list of available sources in the current context
    :ivar default_env: default environment (used to override build='default')
        when simulating a list of action from another machine.
    """

    def __init__(self, spec_repository, default_env=None):
        """Initialize a new context.

        :param spec_repository: an Anod repository
        :type spec_repository: e3.anod.AnodSpecRepository
        :param default_env: an env that should be considered as the
            default for the current context. Mainly useful to simulate
            another server context. If None then we assume that the
            context if the local server
        :type default_env: BaseEnv | None
        """
        self.repo = spec_repository

        if default_env is None:
            self.default_env = BaseEnv()
        else:
            self.default_env = default_env.copy()
        self.tree = DAG()
        self.root = Root()

        self.add(self.root)
        self.cache = {}
        self.sources = {}

    def load(self, name, env, qualifier, kind):
        """Load a spec instance.

        :param name: spec name
        :type name: str
        :param env: environment to use for the spec instance
        :type env: BaseEnv | None
        :param qualifier: spec qualifier
        :type qualifier: str | None
        :param kind: primitive used for the loaded spec
        :type kind: str
        :return: a spec instance
        """
        if env is None:
            env = self.default_env

        # Key used for the spec instance cache
        key = (name, env.build, env.host, env.target, qualifier, kind)

        if key not in self.cache:
            # Spec is not in cache so create a new instance
            self.cache[key] = self.repo.load(name)(qualifier=qualifier,
                                                   env=env,
                                                   kind=kind)

            # Update the list of available sources. ??? Should be done
            # once per spec (and not once per spec instance). Need some
            # spec cleanup to achieve that ???
            if self.cache[key].source_pkg_build is not None:
                for s in self.cache[key].source_pkg_build:
                    self.sources[s.name] = (name, s)

        return self.cache[key]

    def add(self, data, *args):
        """Add node to context tree.

        :param data: node data
        :type data: e3.anod.action.Action
        :param args: list of predecessors
        :type args: e3.anod.action.Action
        """
        preds = [k.uid for k in args]
        self.tree.update_vertex(data.uid, data,
                                predecessors=preds,
                                enable_checks=False)

    def add_decision(self, decision_class, root, left, right):
        """Add a decision node.

        This create the following subtree inside the dag::

            root --> decision --> left
                              |-> right

        :param decision_class: Decision subclass to use
        :type decision_class: () -> Decision
        :param root: parent node of the decision node
        :type root: e3.anod.action.Action
        :param left: left decision (child of Decision node)
        :type left: e3.anod.action.Action
        :param right: right decision (child of Decision node)
        :type right: e3.anod.action.Action
        """
        decision_action = decision_class(root, left, right)
        self.add(decision_action, left, right)
        self.connect(root, decision_action)

    def connect(self, action, *args):
        """Add predecessors to a node.

        :param action: parent node
        :type action: e3.anod.action.Action
        :param args: list of predecessors
        :type args: list[e3.anod.action.Action]
        """
        preds = [k.uid for k in args]
        self.tree.update_vertex(action.uid,
                                predecessors=preds,
                                enable_checks=False)

    def __contains__(self, data):
        """Check if a given action is already in the internal DAG.

        :param data: an Action
        :type data: e3.anod.action.Action
        """
        return data.uid in self.tree

    def __getitem__(self, key):
        """Retrieve action from the internal DAG based on its key.

        :param key: action uid
        :type key: str
        :return: an Action
        :rtype: e3.node.action.Action
        """
        return self.tree[key]

    def predecessors(self, action):
        """Retrieve predecessors of a given action.

        :param action: the parent action
        :type action: e3.anod.action.Action
        :return: the predecessor list
        :rtype: list[e3.anod.action.Action]
        """
        return [self[el] for el in self.tree.vertex_predecessors[action.uid]]

    def add_anod_action(self,
                        name,
                        env=None,
                        primitive=None,
                        qualifier=None,
                        upload=True):
        """Add an Anod action to the context.

        :param name: spec name
        :type name: str
        :param env: spec environment
        :type env: BaseEnv | None
        :param primitive: spec primitive
        :type primitive: str
        :param qualifier: qualifier
        :type qualifier: str | None
        :param upload: if True consider uploading to the store
        :type upload: bool
        :return: the root added action
        :rtype: Action
        """
        # First create the subtree for the spec
        result = self.add_spec(name, env, primitive, qualifier)

        # Resulting subtree should be connected to the root node
        self.connect(self.root, result)

        # Ensure decision is set in case of explicit build or install
        if primitive == 'build':
            build_action = None
            for el in self.predecessors(result):
                if isinstance(el, BuildOrInstall):
                    el.set_decision(BuildOrInstall.BUILD)
                    build_action = self[el.left]
            if build_action is None and isinstance(result, Build):
                build_action = result

            if build_action is not None:
                spec = build_action.data
                if spec.component is not None and upload:
                    if spec.has_package:
                        upload_bin = UploadBinaryComponent(spec)
                    else:
                        upload_bin = UploadSourceComponent(spec)
                    self.add(upload_bin)
                    self.connect(self.root, upload_bin)
                    self.connect(upload_bin, build_action)

        elif primitive == 'install':
            for el in self.predecessors(result):
                if isinstance(el, BuildOrInstall):
                    el.set_decision(BuildOrInstall.INSTALL)
        return result

    def add_spec(self,
                 name,
                 env=None,
                 primitive=None,
                 qualifier=None,
                 expand_build=True,
                 source_name=None):
        """Expand an anod action into a tree (internal).

        :param name: spec name
        :type name: str
        :param env: spec environment
        :type env: BaseEnv | None
        :param primitive: spec primitive
        :type primitive: str
        :param qualifier: qualifier
        :type qualifier: str | None
        :param expand_build: should build primitive be expanded
        :type expand_build: bool
        :param source_name: source name associated with the source
            primitive
        :type source_name: str | None
        """
        # Initialize a spec instance
        spec = self.load(name, qualifier=qualifier, env=env, kind=primitive)

        # Initialize the resulting action based on the primitive name
        if primitive == 'source':
            result = CreateSource(spec, source_name)
        elif primitive == 'build':
            result = Build(spec)
        elif primitive == 'test':
            result = Test(spec)
        elif primitive == 'install':
            result = Install(spec)
        else:  # defensive code
            raise ValueError('add_spec error: %s is not known' % primitive)

        if not spec.has_package and primitive == 'install' and \
                has_primitive(spec, 'build'):
            # Case in which we have an install dependency but no install
            # primitive. In that case the real dependency is a build tree
            # dependency. In case there is no build primitive and no
            # package keep the install primitive (usually this means there
            # is an overloaded download procedure).
            return self.add_spec(name, env, 'build',
                                 qualifier,
                                 expand_build=False)

        if expand_build and primitive == 'build' and \
                spec.has_package:
            # A build primitive is required and the spec defined a binary
            # package. In that case the implicit post action of the build
            # will be a call to the install primitive
            return self.add_spec(name, env, 'install', qualifier)

        # Add this stage if the action is already in the DAG, then it has
        # already been added.
        if result in self:
            return result

        if not has_primitive(spec, primitive):
            raise SchedulingError('spec %s does not support primitive %s'
                                  % (name, primitive))

        # Add the action in the DAG
        self.add(result)

        if primitive == 'install':
            # Expand an install node to
            #    install --> decision --> build
            #                         \-> download binary
            download_action = DownloadBinary(spec)
            self.add(download_action)

            if has_primitive(spec, 'build'):
                build_action = self.add_spec(name,
                                             env,
                                             'build',
                                             qualifier,
                                             expand_build=False)
                self.add_decision(BuildOrInstall,
                                  result,
                                  build_action,
                                  download_action)
            else:
                self.connect(result, download_action)

        # Look for dependencies
        if '%s_deps' % primitive in dir(spec) and \
                getattr(spec, '%s_deps' % primitive) is not None:
            for e in getattr(spec, '%s_deps' % primitive):
                if isinstance(e, Dependency):
                    if e.kind == 'source':
                        # A source dependency does not create a new node but
                        # ensure that sources associated with it are available
                        self.load(e.name, kind='source',
                                  env=BaseEnv(), qualifier=None)
                        continue

                    child_action = self.add_spec(e.name,
                                                 e.env(spec, self.default_env),
                                                 e.kind,
                                                 e.qualifier)

                    spec.deps[e.local_name] = result.anod_instance

                    if e.kind == 'build' and \
                            self[child_action.uid].data.kind == 'install':
                        # We have a build tree dependency that produced a
                        # subtree starting with an install node. In that case
                        # we expect the user to choose BUILD as decision.
                        dec = self.predecessors(child_action)[0]
                        if isinstance(dec, BuildOrInstall):
                            dec.add_trigger(result, BuildOrInstall.BUILD)

                    # Connect child dependency
                    self.connect(result, child_action)

        # Look for source dependencies (i.e sources needed)
        if '%s_source_list' % primitive in dir(spec):
            for s in getattr(spec, '%s_source_list' % primitive):
                # set source builder
                if s.name in self.sources:
                    s.set_builder(self.sources[s.name])
                # add source install node
                src_install_uid = result.uid.rsplit('.', 1)[0] + \
                    '.source_install.' + s.name
                src_install_action = InstallSource(src_install_uid, spec, s)
                self.add(src_install_action)
                self.connect(result, src_install_action)

                # Then add nodes to create that source (download or creation
                # using anod source and checkouts)
                if s.name in self.sources:
                    spec_decl, obj = self.sources[s.name]
                else:
                    raise AnodError(
                        origin='expand_spec',
                        message='source %s does not exist '
                        '(referenced by %s)' % (s.name, result.uid))

                src_get_action = GetSource(obj)
                if src_get_action in self:
                    self.connect(src_install_action, src_get_action)
                    continue

                self.add(src_get_action)
                self.connect(src_install_action, src_get_action)
                src_download_action = DownloadSource(obj)
                self.add(src_download_action)

                if isinstance(obj, UnmanagedSourceBuilder):
                    # In that case only download is available
                    self.connect(src_get_action, src_download_action)
                else:
                    source_action = self.add_spec(spec_decl,
                                                  BaseEnv(),
                                                  'source',
                                                  None,
                                                  source_name=s.name)
                    for repo in obj.checkout:
                        r = Checkout(repo, self.repo.repos.get(repo))
                        self.add(r)
                        self.connect(source_action, r)
                    self.add_decision(CreateSourceOrDownload,
                                      src_get_action,
                                      source_action,
                                      src_download_action)

        return result

    @classmethod
    def decision_error(cls, action, decision):
        """Raise SchedulingError.

        :param action: action to consider
        :type action: Action
        :param decision: decision to resolve
        :type decision: Decision
        :raise SchedulingError
        """
        if decision.choice is None:
            msg = 'a decision should be taken between %s%s and %s%s' % (
                decision.left,
                ' (expected)' if decision.expected_choice == Decision.LEFT
                else '',
                decision.right,
                ' (expected)' if decision.expected_choice == Decision.RIGHT
                else '')
        elif decision.choice == Decision.BOTH:
            msg = 'cannot do both %s and %s' % (decision.left, decision.right)
        else:
            msg = 'cannot do %s as %s is expected after ' \
                  'scheduling resolution' % \
                  (action.uid, decision.get_expected_decision())
        raise SchedulingError(msg)

    @classmethod
    def always_download_source_resolver(cls, action, decision):
        """Force source download when scheduling a plan.

        The resolver takes the following decision:
        * sources are always downloaded
        * any build that produces a package should be added explicitly

        :param action: action to consider
        :type action: Action
        :param decision: decision to resolve
        :type decision: Decision
        :return: True if the action should be scheduled, False otherwise
        :rtype: False
        :raise SchedulingError: in case no decision can be taken
        """
        if isinstance(action, CreateSource):
            return False
        elif isinstance(action, DownloadSource):
            return True
        else:
            return cls.decision_error(action, decision)

    @classmethod
    def always_create_source_resolver(cls, action, decision):
        """Force source creation when scheduling a plan."""
        if isinstance(action, CreateSource):
            return True
        elif isinstance(action, DownloadSource):
            return False
        else:
            return cls.decision_error(action, decision)

    def schedule(self, resolver):
        """Compute a DAG of scheduled actions.

        :param resolver: a function that helps the scheduler resolve cases
            for which a decision should be taken
        :type resolver: (Action, Decision) -> bool
        """
        rev = self.tree.reverse_graph()
        uploads = []
        dag = DAG()

        for uid, action in rev:
            if uid == 'root':
                # Root node is always in the final DAG
                dag.add_vertex(uid, action)
            elif isinstance(action, Decision):
                # Decision node does not appears in the final DAG but we need
                # to apply the triggers based on the current list of scheduled
                # actions.
                action.apply_triggers(dag)
            elif isinstance(action, UploadComponent):
                uploads.append((action,
                                self.tree.vertex_predecessors[uid]))
            else:
                # Compute the list of successors for the current node (i.e:
                # predecessors in the reversed graph). Ignore UploadComponent
                # nodes as they will be processed only once the scheduling
                # is done.
                preds = list([k for k in rev.vertex_predecessors[uid]
                              if not isinstance(rev[k], UploadComponent)])

                if len(preds) == 1 and isinstance(rev[preds[0]], Decision):
                    decision = rev[preds[0]]
                    # The current node addition is driven by a decision

                    # First check that the parent of the decision is
                    # scheduled. If not discard the item.
                    if decision.initiator not in dag:
                        continue

                    # Now check decision made. If the decision cannot be made
                    # delegate to the resolve function.
                    choice = decision.get_decision()

                    if choice == uid:
                        dag.add_vertex(uid, action)
                        dag.update_vertex(decision.initiator,
                                          predecessors=[uid],
                                          enable_checks=False)
                    elif choice is None:
                        # delegate to resolver
                        try:
                            if resolver(action, decision):
                                dag.add_vertex(uid, action)
                                dag.update_vertex(decision.initiator,
                                                  predecessors=[uid],
                                                  enable_checks=False)
                        except SchedulingError as e:
                            # In order to help the analysis of a scheduling
                            # error compute the explicit initiators of that
                            # action
                            dag.add_vertex(uid, action)
                            dag.update_vertex(decision.initiator,
                                              predecessors=[action.uid],
                                              enable_checks=False)
                            rev_graph = dag.reverse_graph()
                            # Initiators are explicit actions (connected to
                            # 'root') that are in the closure of the failing
                            # node.
                            initiators = [
                                iuid for iuid in rev_graph.get_closure(uid)
                                if 'root'
                                in rev_graph.vertex_predecessors[iuid]]
                            raise SchedulingError(e.messages, uid=uid,
                                                  initiators=initiators)
                else:
                    # An action is scheduled only if one of its successors is
                    # scheduled.
                    successors = [k for k in preds if k in dag]
                    if successors:
                        dag.add_vertex(uid, action)
                        for a in successors:
                            dag.update_vertex(a,
                                              predecessors=[uid],
                                              enable_checks=False)

        # Handle UploadComponent nodes. Add the node only if all predecessors
        # are scheduled.
        for action, predecessors in uploads:
            if len([p for p in predecessors if p not in dag]) == 0:
                dag.update_vertex(action.uid,
                                  action,
                                  predecessors=predecessors,
                                  enable_checks=False)
                # connect upload to the root node
                dag.update_vertex('root', predecessors=[action.uid])
        return dag
