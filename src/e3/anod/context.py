from __future__ import annotations

from typing import TYPE_CHECKING
import e3.log
from e3.anod.action import (
    Build,
    BuildOrDownload,
    Checkout,
    CreateSource,
    CreateSourceOrDownload,
    CreateSources,
    Decision,
    DownloadBinary,
    DownloadSource,
    GetSource,
    Install,
    InstallSource,
    Root,
    Test,
    Upload,
    UploadBinaryComponent,
    UploadSource,
    UploadSourceComponent,
)
from e3.anod.deps import Dependency
from e3.anod.error import AnodError
from e3.anod.package import UnmanagedSourceBuilder
from e3.anod.spec import has_primitive, fetch_attr
from e3.collection.dag import DAG
from e3.electrolyt.plan import PlanActionEnv
from e3.env import BaseEnv
from e3.error import E3Error

if TYPE_CHECKING:
    from typing import (
        cast,
        Callable,
        Dict,
        FrozenSet,
        List,
        NoReturn,
        Optional,
        Tuple,
    )
    from e3.anod.action import Action
    from e3.anod.package import SourceBuilder
    from e3.anod.spec import Anod, PRIMITIVE
    from e3.anod.loader import AnodSpecRepository
    from e3.anod.sandbox import SandBox
    from e3.collection.dag import VertexID
    from e3.platform import Platform
    from e3.mypy import assert_never

    # spec name, build env, target env, host env, qualifier, kind, source name
    CacheKeyType = Tuple[
        str, Platform, Platform, Platform, Optional[str], Optional[str], Optional[str]
    ]
    ResolverType = Callable[[Action, Decision], bool]


logger = e3.log.getLogger("anod.context")


class SchedulingError(E3Error):
    """Exception raised by scheduling algorithm."""

    def __init__(
        self,
        message: str | List[str],
        origin: Optional[str] = None,
        uid: Optional[VertexID] = None,
        initiators: Optional[List[VertexID]] = None,
    ):
        """Scheduling error initialization.

        :param message: the exception message
        :param origin: the name of the function, class, or module having raised
            the exception
        :param uid: uid of action that cause the error
        :param initiators: list of uids involved in the failure
        """
        super().__init__(message, origin)
        self.uid = uid
        self.initiators = initiators if initiators is not None else []


class AnodContext:
    """Anod context.

    :ivar repo: an anod spec repository
    :vartype repo: e3.anod.loader.AnodSpecRepository
    :ivar tree: a DAG containing the list of possible actions
    :ivar root: root node of the DAG
    :ivar cache: cache of anod instances, indexed by the spec's name.
    :vartype cache: dict[e3.anod.spec.Anod]
    :ivar sources: list of available sources in the current context,
        indexed by the source's name.
    :vartype sources: list[e3.anod.package.SourceBuilder]
    :ivar default_env: default environment (used to override build='default')
        when simulating a list of action from another machine.

    :ivar plan: maintain a link between a plan line and the generated actions
        which is useful for setting parameters such as weather or process that
        are conveyed by the plan and not by the specs
    """

    def __init__(
        self,
        spec_repository: AnodSpecRepository,
        default_env: Optional[BaseEnv] = None,
        reject_duplicates: bool = False,
    ):
        """Initialize a new context.

        :param spec_repository: an Anod repository
        :param default_env: an env that should be considered as the
            default for the current context. Mainly useful to simulate
            another server context. If None then we assume that the
            context if the local server
        :param reject_duplicates: if True, raise SchedulingError when two
            duplicated action are generated
        """
        self.repo = spec_repository
        if default_env is None:
            self.default_env = BaseEnv()
        else:
            self.default_env = default_env.copy()
        self.reject_duplicates = reject_duplicates

        self.tree = DAG()
        self.root = Root()
        self.dependencies: Dict[str, Dict[str, Tuple[Dependency, Anod]]] = {}
        self.add(self.root)
        self.cache: Dict[CacheKeyType, Anod] = {}
        self.sources: Dict[str, Tuple[str, SourceBuilder]] = {}

    def load(
        self,
        name: str,
        env: Optional[BaseEnv],
        qualifier: Optional[str],
        kind: PRIMITIVE,
        sandbox: Optional[SandBox] = None,
        source_name: Optional[str] = None,
    ) -> Anod:
        """Load a spec instance.

        :param name: spec name
        :param env: environment to use for the spec instance
        :param qualifier: spec qualifier
        :param kind: primitive used for the loaded spec
        :param sandbox: is not None bind the anod instances to a sandbox
        :param source_name: when the primitive is "source" we create a specific
            instance for each source package we have to create.
        :return: a spec instance
        """
        if env is None:
            env = self.default_env

        # Key used for the spec instance cache
        key = (name, env.build, env.host, env.target, qualifier, kind, source_name)

        if key not in self.cache:
            # Spec is not in cache so create a new instance
            self.cache[key] = self.repo.load(name)(
                qualifier=qualifier, env=env, kind=kind
            )
            if sandbox is not None:
                self.cache[key].bind_to_sandbox(sandbox)

            # Update tracking of dependencies
            self.dependencies[self.cache[key].uid] = {}

            # Update the list of available sources. ??? Should be done
            # once per spec (and not once per spec instance). Need some
            # spec cleanup to achieve that ???
            source_builders = self.cache[key].source_pkg_build
            if source_builders is not None:
                for s in source_builders:
                    self.sources[s.name] = (name, s)

        return self.cache[key]

    def add(self, data: Action, *args: Action) -> None:
        """Add node to context tree.

        :param data: node data
        :param args: list of predecessors
        """
        preds = [k.uid for k in args]
        self.tree.update_vertex(data.uid, data, predecessors=preds, enable_checks=False)

    def add_decision(
        self,
        decision_class: Callable[..., Decision],
        root: Action,
        left: Action,
        right: Action,
    ) -> None:
        """Add a decision node.

        This create the following subtree inside the dag::

            root --> decision --> left
                              |-> right

        :param decision_class: Decision subclass to use
        :param root: parent node of the decision node
        :param left: left decision (child of Decision node)
        :param right: right decision (child of Decision node)
        """
        decision_action = decision_class(root, left, right)
        self.add(decision_action, left, right)
        self.connect(root, decision_action)

    def connect(self, action: Action, *args: Action) -> None:
        """Add predecessors to a node.

        :param action: parent node
        :param args: list of predecessors
        """
        preds = [k.uid for k in args]
        self.tree.update_vertex(action.uid, predecessors=preds, enable_checks=False)

    def __contains__(self, data: Action) -> bool:
        """Check if a given action is already in the internal DAG.

        :param data: an Action
        """
        return data.uid in self.tree

    def __getitem__(self, key: str) -> Action:
        """Retrieve action from the internal DAG based on its key.

        :param key: action uid
        :return: an Action
        """
        return self.tree[key]

    def predecessors(self, action: Action) -> List[Action]:
        """Retrieve predecessors of a given action.

        :param action: the parent action
        :return: the predecessor list
        """
        return [self[str(el)] for el in self.tree.get_predecessors(action.uid)]

    def link_to_plan(self, vertex_id: str, plan_line: str, plan_args: dict) -> None:
        """Tag the vertex with plan info.

        :param vertex_id: ID of the vertex
        :param plan_line: corresponding line:linenumber in the plan
        :param plan_args: action args after plan execution, taking into
            account plan context (such as with defaults(XXX):)
        """
        if self.reject_duplicates:
            previous_tag = self.tree.get_tag(vertex_id=vertex_id)
            if previous_tag and previous_tag["plan_line"] != plan_line:
                raise SchedulingError(
                    "entries {} and {} conflict because they result in "
                    "the same build space (id: {}). Check your "
                    "build_space_name property or your qualifiers".format(
                        previous_tag["plan_line"], plan_line, vertex_id
                    )
                )
        self.tree.add_tag(vertex_id, {"plan_line": plan_line, "plan_args": plan_args})

    def add_plan_action(
        self, plan_action_env: PlanActionEnv, sandbox: Optional[SandBox] = None
    ) -> Optional[Action]:
        """Add an Anod action to the context.

        :param plan_action_env: the PlanActionEnv object as returned by PlanContext
        :param sandbox: the SandBox object that will be used to run commands
        :return: the root added action or None if this is not an anod action
        """
        action_name = plan_action_env.action
        if not action_name.startswith("anod_") or plan_action_env.module is None:
            return None

        primitive = action_name.replace("anod_", "", 1)
        if (
            primitive != "build"
            and primitive != "install"
            and primitive != "test"
            and primitive != "source"
        ):
            logger.warning(f"Unknown primtive {primitive}")
            return None
        elif TYPE_CHECKING:
            primitive = cast(PRIMITIVE, primitive)

        return self.add_anod_action(
            name=plan_action_env.module,
            env=self.default_env
            if plan_action_env.default_build
            else BaseEnv.from_env(plan_action_env),
            primitive=primitive,
            qualifier=plan_action_env.qualifier,
            source_packages=plan_action_env.source_packages,
            upload=plan_action_env.push_to_store,
            plan_line=plan_action_env.plan_line,
            plan_args=plan_action_env.plan_args,
            sandbox=sandbox,
        )

    def add_anod_action(
        self,
        name: str,
        env: BaseEnv,
        primitive: PRIMITIVE,
        qualifier: Optional[str] = None,
        source_packages: Optional[List[str]] = None,
        upload: bool = True,
        plan_line: Optional[str] = None,
        plan_args: Optional[dict] = None,
        sandbox: Optional[SandBox] = None,
    ) -> Action:
        """Add an Anod action to the context (internal function).

        Note that using add_anod_action should be avoided when possible
        and replaced by a call to add_plan_action.

        :param name: spec name
        :param env: context in which to load the spec
        :param primitive: spec primitive
        :param qualifier: qualifier
        :param source_packages: if not empty only create the specified list of
            source packages and not all source packages defined in the anod
            specification file
        :param upload: if True consider uploading to the store
        :param plan_line: corresponding line:linenumber in the plan
        :param plan_args: action args after plan execution, taking into
            account plan context (such as with defaults(XXX):)
        :param sandbox: the SandBox object that will be used to run commands
        :return: the root added action
        """
        # First create the subtree for the spec
        result = self.add_spec(
            name,
            env,
            primitive,
            qualifier,
            source_packages=source_packages,
            plan_line=plan_line,
            plan_args=plan_args,
            sandbox=sandbox,
            upload=upload,
        )

        # Resulting subtree should be connected to the root node
        self.connect(self.root, result)

        # Ensure decision is set in case of explicit build or install
        if primitive == "build":
            build_action = None
            for el in self.predecessors(result):
                if isinstance(el, BuildOrDownload):
                    el.set_decision(BuildOrDownload.BUILD, plan_line)
                    build_action = self[el.left]
            if build_action is None and isinstance(result, Build):
                build_action = result

            # Create upload nodes
            if build_action is not None:
                spec = build_action.data
                if spec.component is not None and upload:
                    upload_bin: UploadBinaryComponent | UploadSourceComponent
                    if spec.has_package:
                        upload_bin = UploadBinaryComponent(spec)
                    else:
                        upload_bin = UploadSourceComponent(spec)
                    self.add(upload_bin)
                    # ??? is it needed?
                    if plan_line is not None and plan_args is not None:
                        self.link_to_plan(
                            vertex_id=upload_bin.uid,
                            plan_line=plan_line,
                            plan_args=plan_args,
                        )
                    self.connect(self.root, upload_bin)
                    self.connect(upload_bin, build_action)

        elif primitive == "install":
            for el in self.predecessors(result):
                if isinstance(el, BuildOrDownload):
                    el.set_decision(BuildOrDownload.INSTALL, plan_line)
        elif primitive != "source" and primitive != "test":
            assert_never()
        return result

    def add_spec(
        self,
        name: str,
        env: BaseEnv,
        primitive: PRIMITIVE,
        qualifier: Optional[str] = None,
        source_packages: Optional[List[str]] = None,
        expand_build: bool = True,
        source_name: Optional[str] = None,
        plan_line: Optional[str] = None,
        plan_args: Optional[dict] = None,
        sandbox: Optional[SandBox] = None,
        upload: bool = False,
    ) -> Build | CreateSources | CreateSource | Install | Test:
        """Expand an anod action into a tree (internal).

        :param name: spec name
        :param env: context in which to load the spec
        :param primitive: spec primitive
        :param qualifier: qualifier
        :param source_packages: if not empty only create the specified list of
            source packages and not all source packages defined in the anod
            specification file
        :param expand_build: should build primitive be expanded
        :param source_name: source name associated with the source
            primitive
        :param plan_line: corresponding line:linenumber in the plan
        :param plan_args: action args after plan execution, taking into
            account plan context (such as with defaults(XXX):)
        :param sandbox: if not None, anod instance are automatically bind to
            the given sandbox
        :param upload: if True consider uploads to the store (sources and
            binaries)
        """

        def add_action(data: Action, connect_with: Optional[Action] = None) -> None:
            self.add(data)
            if connect_with is not None:
                self.connect(connect_with, data)

        def add_dep(spec_instance: Anod, dep: Dependency, dep_instance: Anod) -> None:
            """Add a new dependency in an Anod instance dependencies dict.

            :param spec_instance: an Anod instance
            :param dep: the dependency we want to add
            :param dep_instance: the Anod instance loaded for that dependency
            """
            if dep.local_name in spec_instance.deps:
                raise AnodError(
                    origin="expand_spec",
                    message="The spec {} has two dependencies with the same "
                    "local_name attribute ({})".format(
                        spec_instance.name, dep.local_name
                    ),
                )
            spec_instance.deps[dep.local_name] = dep_instance

        # Initialize a spec instance
        e3.log.debug(
            "add spec: name:{}, qualifier:{}, primitive:{}".format(
                name, qualifier, primitive
            )
        )
        spec = self.load(
            name,
            qualifier=qualifier,
            env=env,
            kind=primitive,
            sandbox=sandbox,
            source_name=source_name,
        )
        result: Build | CreateSources | CreateSource | Install | Test

        # Initialize the resulting action based on the primitive name
        if primitive == "source":
            if not has_primitive(spec, "source"):
                raise SchedulingError(f"spec {name} does not support primitive source")

            if source_name is not None:
                result = CreateSource(spec, source_name)

            else:
                # Create the root node
                result = CreateSources(spec)

                # A consequence of calling add_action here
                # will result in skipping dependencies parsing.
                add_action(result)

                if TYPE_CHECKING:
                    # When creating sources we know that the
                    # source_pkg_build attribute is set
                    assert spec.source_pkg_build is not None

                # Then one node for each source package
                for sb in spec.source_pkg_build:
                    if source_packages and sb.name not in source_packages:
                        # This source package is defined in the spec but
                        # explicitly excluded in the plan
                        continue
                    if isinstance(sb, UnmanagedSourceBuilder):
                        # do not create source package for unmanaged source
                        continue
                    sub_result = self.add_spec(
                        name=name,
                        env=env,
                        primitive="source",
                        source_name=sb.name,
                        plan_line=plan_line,
                        plan_args=plan_args,
                        sandbox=sandbox,
                        upload=upload,
                    )
                    self.connect(result, sub_result)

        elif primitive == "build":
            result = Build(spec)
        elif primitive == "test":
            result = Test(spec)
        elif primitive == "install":
            result = Install(spec)
        else:
            assert_never()

        # If this action is directly linked with a plan line make sure
        # to register the link between the action and the plan even
        # if the action has already been added via another dependency
        if plan_line is not None and plan_args is not None:
            self.link_to_plan(
                vertex_id=result.uid, plan_line=plan_line, plan_args=plan_args
            )

        if (
            primitive == "install"
            and not spec.has_package
            and has_primitive(spec, "build")
        ):
            if plan_line is not None and plan_args is not None:
                # We have an explicit call to install() in the plan but the
                # spec has no binary package to download.
                raise SchedulingError(
                    f"error in plan at {plan_line}: "
                    "install should be replaced by build - "
                    f"the spec {spec.name} has a build primitive "
                    "but does not define a package"
                )
            # Case in which we have an install dependency but no install
            # primitive. In that case the real dependency is a build tree
            # dependency. In case there is no build primitive and no
            # package keep the install primitive (usually this means there
            # is an overloaded download procedure).
            return self.add_spec(
                name,
                env,
                "build",
                qualifier,
                expand_build=False,
                plan_args=plan_args,
                plan_line=plan_line,
                sandbox=sandbox,
                upload=upload,
            )

        if expand_build and primitive == "build" and spec.has_package:
            # A build primitive is required and the spec defined a binary
            # package. In that case the implicit post action of the build
            # will be a call to the install primitive
            return self.add_spec(
                name,
                env,
                "install",
                qualifier,
                plan_args=None,
                plan_line=plan_line,
                sandbox=sandbox,
                upload=upload,
            )

        # Add this stage if the action is already in the DAG, then it has
        # already been added.
        if result in self:
            return result

        if not has_primitive(spec, primitive):
            raise SchedulingError(f"spec {name} does not support primitive {primitive}")

        # Add the action in the DAG
        add_action(result)

        if primitive == "install":
            # Expand an install node to
            #    install --> decision --> build
            #                         \-> download binary
            download_action = DownloadBinary(spec)
            add_action(download_action)

            if has_primitive(spec, "build"):
                build_action = self.add_spec(
                    name=name,
                    env=env,
                    primitive="build",
                    qualifier=qualifier,
                    expand_build=False,
                    plan_args=None,
                    plan_line=plan_line,
                    sandbox=sandbox,
                    upload=upload,
                )
                self.add_decision(
                    BuildOrDownload, result, build_action, download_action
                )
            else:
                self.connect(result, download_action)

        elif primitive == "source":
            if source_name is not None:
                # Also add an UploadSource action
                if upload:
                    upload_src = UploadSource(spec, source_name)
                    self.add(upload_src)
                    # Link the upload to the current context
                    if plan_line is not None and plan_args is not None:
                        self.link_to_plan(
                            vertex_id=upload_src.uid,
                            plan_line=plan_line,
                            plan_args=plan_args,
                        )

                    self.connect(self.root, upload_src)
                    self.connect(upload_src, result)

                if TYPE_CHECKING:
                    # When creating sources we know that the
                    # source_pkg_build attribute is set
                    assert spec.source_pkg_build is not None
                for sb in spec.source_pkg_build:
                    if sb.name == source_name:
                        for checkout in sb.checkout:
                            if checkout not in self.repo.repos:
                                raise SchedulingError(
                                    origin="add_spec",
                                    message=f"unknown repository {checkout}",
                                )
                            co = Checkout(checkout, self.repo.repos[checkout])
                            add_action(co, result)

        # Look for dependencies. Consider that "None" means "no dependency".
        spec_dependencies = list(fetch_attr(spec, f"{primitive}_deps", None) or [])

        source_spec_dependencies_names = {
            d.name for d in spec_dependencies if d.kind == "source"
        }

        for e in spec_dependencies:
            if isinstance(e, Dependency):
                if e.kind == "source":
                    # A source dependency does not create a new node but
                    # ensure that sources associated with it are available
                    child_instance = self.load(
                        e.name,
                        kind="source",
                        env=self.default_env,
                        qualifier=None,
                        sandbox=sandbox,
                    )
                    add_dep(spec_instance=spec, dep=e, dep_instance=child_instance)
                    self.dependencies[spec.uid][e.local_name] = (
                        e,
                        spec.deps[e.local_name],
                    )

                    continue

                child_action = self.add_spec(
                    name=e.name,
                    env=e.env(spec, self.default_env),
                    primitive=e.kind,
                    qualifier=e.qualifier,
                    plan_args=None,
                    plan_line=plan_line,
                    sandbox=sandbox,
                    upload=upload,
                )

                add_dep(
                    spec_instance=spec, dep=e, dep_instance=child_action.anod_instance
                )
                self.dependencies[spec.uid][e.local_name] = (e, spec.deps[e.local_name])

                if e.kind == "build" and self[child_action.uid].data.kind == "install":
                    # We have a build tree dependency that produced a
                    # subtree starting with an install node. In that case
                    # we expect the user to choose BUILD as decision.
                    child_action_preds = self.predecessors(child_action)
                    if child_action_preds:
                        dec = child_action_preds[0]
                        if isinstance(dec, BuildOrDownload):
                            dec.add_trigger(
                                result,
                                BuildOrDownload.BUILD,
                                plan_line if plan_line is not None else "unknown line",
                            )

                # Connect child dependency
                self.connect(result, child_action)

        # Look for source dependencies (i.e sources needed)
        source_list = fetch_attr(spec, f"{primitive}_source_list", None)
        if source_list is not None:
            for s in source_list:
                # set source builder
                if s.name in self.sources:
                    sb_spec, sb = self.sources[s.name]
                    if (
                        sb_spec != spec.name
                        and sb_spec not in source_spec_dependencies_names
                        # ignore unmanaged source builders which do not
                        # create many issues (no need to find the source
                        # builder to apply patches, update repositories, ...)
                        # and this creates too many warnings in production that
                        # we do not have time to fix
                        and not isinstance(sb, UnmanagedSourceBuilder)
                    ):
                        logger.warning(
                            f"{spec.name}.anod ({primitive}): source {s.name}"
                            f" coming from {sb_spec} but there is no"
                            f" source_pkg dependency for {sb_spec} in {primitive}_deps",
                        )
                    s.set_builder(sb)

                # set other sources to compute source ignore
                s.set_other_sources(source_list)
                # add source install node
                src_install_uid = (
                    result.uid.rsplit(".", 1)[0] + ".source_install." + s.name
                )
                src_install_action = InstallSource(src_install_uid, spec, s)
                add_action(src_install_action, connect_with=result)

                # Then add nodes to create that source (download or creation
                # using anod source and checkouts)
                if s.name in self.sources:
                    spec_decl, obj = self.sources[s.name]
                else:
                    raise AnodError(
                        origin="expand_spec",
                        message="source %s does not exist "
                        "(referenced by %s)" % (s.name, result.uid),
                    )

                src_get_action = GetSource(obj)
                if src_get_action in self:
                    self.connect(src_install_action, src_get_action)
                    continue

                add_action(src_get_action, connect_with=src_install_action)

                src_download_action = DownloadSource(obj)
                add_action(src_download_action)

                if isinstance(obj, UnmanagedSourceBuilder):
                    # In that case only download is available
                    self.connect(src_get_action, src_download_action)
                else:
                    source_action = self.add_spec(
                        name=spec_decl,
                        env=self.default_env,
                        primitive="source",
                        plan_args=None,
                        plan_line=plan_line,
                        source_name=s.name,
                        sandbox=sandbox,
                        upload=upload,
                    )
                    for repo in obj.checkout:
                        r = Checkout(repo, self.repo.repos[repo])
                        add_action(r, connect_with=source_action)
                    self.add_decision(
                        CreateSourceOrDownload,
                        src_get_action,
                        source_action,
                        src_download_action,
                    )
        return result

    @classmethod
    def decision_error(cls, action: Action, decision: Decision) -> NoReturn:
        """Raise SchedulingError.

        :param action: action to consider
        :param decision: decision to resolve
        :raise: SchedulingError
        """
        if decision.choice is None and decision.expected_choice in (
            Decision.LEFT,
            Decision.RIGHT,
        ):

            if decision.expected_choice == BuildOrDownload.BUILD:
                msg = (
                    "A spec in the plan has a build_tree dependency"
                    " on {spec}. Either explicitly add the line {plan_line}"
                    " or change the dependency to set"
                    ' require="installation" if possible'.format(
                        spec=action.data.name,
                        plan_line=decision.suggest_plan_fix(decision.expected_choice),
                    )
                )
            else:
                msg = "This plan resolver requires an explicit {}".format(
                    decision.suggest_plan_fix(decision.expected_choice)
                )
        elif decision.choice is None and decision.expected_choice is None:
            left_decision = decision.suggest_plan_fix(Decision.LEFT)
            right_decision = decision.suggest_plan_fix(Decision.RIGHT)
            msg = (
                "This plan resolver cannot decide whether what to do for"
                " resolving {}.".format(decision.initiator)
            )
            if left_decision is not None and right_decision is not None:
                msg += " Please either add {} or {} in the plan".format(
                    left_decision, right_decision
                )
        elif decision.choice == Decision.BOTH:
            msg = f"cannot do both {decision.left} and {decision.right}"
        else:
            trigger_decisions = "\n".join(
                "{} made by {} initiated by {}".format(
                    decision.left
                    if trigger_decision == Decision.LEFT
                    else decision.right,
                    trigger_action,
                    trigger_plan_line,
                )
                for (
                    trigger_action,
                    trigger_decision,
                    trigger_plan_line,
                ) in decision.triggers
            )
            conflict_choice = decision.choice
            if TYPE_CHECKING:
                # we expect the decision to be either LEFT or RIGHT
                # at this stage
                assert conflict_choice is not None
            msg = (
                "explicit {} decision made by {} conflicts with the "
                "following decision{}:\n{}".format(
                    decision.description(conflict_choice),
                    decision.decision_maker,
                    "s" if len(decision.triggers) > 1 else "",
                    trigger_decisions,
                )
            )

        raise SchedulingError(msg)

    @classmethod
    def always_download_source_resolver(
        cls, action: Action, decision: Decision
    ) -> bool:
        """Force source download when scheduling a plan.

        The resolver takes the following decision:
        * sources are always downloaded
        * any build that produces a package should be added explicitly

        :param action: action to consider
        :param decision: decision to resolve
        :return: True if the action should be scheduled, False otherwise
        :raise SchedulingError: in case no decision can be taken
        """
        if isinstance(action, CreateSource):
            return False
        elif isinstance(action, DownloadSource):
            return True
        else:
            return cls.decision_error(action, decision)

    @classmethod
    def always_create_source_resolver(cls, action: Action, decision: Decision) -> bool:
        """Force source creation when scheduling a plan."""
        if isinstance(action, CreateSource):
            return True
        elif isinstance(action, DownloadSource):
            return False
        else:
            return cls.decision_error(action, decision)

    def schedule(self, resolver: ResolverType) -> DAG:
        """Compute a DAG of scheduled actions.

        :param resolver: a function that helps the scheduler resolve cases
            for which a decision should be taken
        """
        rev = self.tree.reverse_graph(enable_checks=False)
        uploads: List[Tuple[Upload, FrozenSet[VertexID]]] = []
        dag = DAG()

        # Retrieve existing tags
        dag.tags = self.tree.tags

        # Note that schedule perform a pruning on the DAG, thus no cycle can
        # be introduced. That's why checks are disabled when creating the
        # result graph.
        for uid, action in rev:
            if TYPE_CHECKING:
                assert uid is not None
            if uid == "root":
                # Root node is always in the final DAG
                dag.update_vertex(uid, action, enable_checks=False)
            elif isinstance(action, Decision):
                # Decision node does not appears in the final DAG but we need
                # to apply the triggers based on the current list of scheduled
                # actions.
                action.apply_triggers(dag)
            elif isinstance(action, Upload):
                uploads.append((action, self.tree.get_predecessors(uid)))
            else:
                if TYPE_CHECKING:
                    assert isinstance(action, Action)
                # Compute the list of successors for the current node (i.e:
                # predecessors in the reversed graph). Ignore Upload
                # nodes as they will be processed only once the scheduling
                # is done.
                preds = [
                    k
                    for k in rev.get_predecessors(uid)
                    if not isinstance(rev[k], Upload)
                ]

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
                        dag.update_vertex(uid, action, enable_checks=False)
                        dag.update_vertex(
                            decision.initiator, predecessors=[uid], enable_checks=False
                        )
                    elif choice is None:
                        # delegate to resolver
                        try:
                            if resolver(action, decision):
                                dag.update_vertex(uid, action, enable_checks=False)
                                dag.update_vertex(
                                    decision.initiator,
                                    predecessors=[uid],
                                    enable_checks=False,
                                )
                        except SchedulingError as e:
                            # In order to help the analysis of a scheduling
                            # error compute the explicit initiators of that
                            # action
                            dag.update_vertex(uid, action, enable_checks=False)
                            dag.update_vertex(
                                decision.initiator,
                                predecessors=[action.uid],
                                enable_checks=False,
                            )
                            rev_graph = dag.reverse_graph()
                            # Initiators are explicit actions (connected to
                            # 'root') that are in the closure of the failing
                            # node.
                            initiators = [
                                iuid
                                for iuid in rev_graph.get_closure(uid)
                                if "root" in rev_graph.get_predecessors(iuid)
                            ]
                            raise SchedulingError(
                                e.messages, uid=uid, initiators=initiators
                            )
                else:
                    # An action is scheduled only if one of its successors is
                    # scheduled.
                    successors = [k for k in preds if k in dag]
                    if successors:
                        dag.update_vertex(uid, action, enable_checks=False)
                        for a in successors:
                            dag.update_vertex(
                                a, predecessors=[uid], enable_checks=False
                            )

        # Handle Upload nodes. Add the node only if all predecessors
        # are scheduled.
        for action, predecessors in uploads:
            if len([p for p in predecessors if p not in dag]) == 0:
                dag.update_vertex(
                    action.uid, action, predecessors=predecessors, enable_checks=False
                )
                # connect upload to the root node
                dag.update_vertex(
                    "root", predecessors=[action.uid], enable_checks=False
                )
        return dag
