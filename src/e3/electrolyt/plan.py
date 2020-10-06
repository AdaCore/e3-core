from __future__ import annotations

import ast
import inspect
import types
from datetime import datetime, timezone
from functools import partial
from typing import TYPE_CHECKING

from e3.collection.toggleable_bool import ToggleableBooleanGroup
from e3.electrolyt.entry_point import Machine, entry_point
from e3.env import BaseEnv
from e3.error import E3Error

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, Callable, Dict, List, Optional, Type
    from e3.collection.toggleable_bool import ToggleableBoolean
    from e3.electrolyt.entry_point import EntryPoint


class PlanError(E3Error):
    """Error when parsing or executing the plan."""

    pass


class Plan:
    """Electrolyt Plan.

    :ivar entry_points: list of entry points found in the plans
    :vartype entry_points: dict
    """

    def __init__(
        self,
        data: Dict[str, Any],
        entry_point_cls: Optional[Dict[str, Callable[..., EntryPoint]]] = None,
        plan_ext: str = ".plan",
    ):
        """Initialize a new plan.

        :param data: a dictionary defining additional globals to push
            into plan associated module
        :param entry_point_cls: dict associating a list of decorator name
            with an entry point class
        :param plan_ext: plan extension, by default ".plan". This is used to
            detect whether a specific frame is in a plan or in our code. See
            PlanContext._add_action
        """
        self.mod = types.ModuleType("_anod_plan_")

        # Some additional user symbols
        for k, v in data.items():
            self.mod.__dict__[k] = v

        self.entry_points: Dict[str, EntryPoint] = {}

        if entry_point_cls is None:
            entry_point_cls = {}

        self.plan_ext = plan_ext

        self.mod.__dict__["machine"] = partial(
            entry_point, self.entry_points, Machine, "machine"
        )

        for name, cls in entry_point_cls.items():
            self.mod.__dict__[name] = partial(entry_point, self.entry_points, cls, name)

        self.plan_date = datetime.now(timezone.utc)
        self.mod.__dict__["cond"] = self.cond
        self.toggleable_bool_group = ToggleableBooleanGroup()

    def cond(self, name: str, date: Callable[[datetime], bool]) -> ToggleableBoolean:
        """Generate a new conditional boolean.

        :param name: variable name
        :param date: function that takes the plan date and return a boolean.
            This can be used to set a value depending on the day of the week,
            e.g. by setting the constant to True on weekend:
            lambda d: d.isoweekday() in [6, 7]
        """
        return self.toggleable_bool_group.add(name, date(self.plan_date))

    def load(self, filename: str) -> None:
        """Load python code from file.

        :param filename: path to the python code
        """
        with open(filename, "rb") as fd:
            source_code = fd.read()
        self.load_chunk(source_code, filename)

    def check(self, code_ast: ast.AST) -> None:
        """Check plan coding style."""
        del self, code_ast

    def load_chunk(self, source_code: bytes, filename: str = "<unknown>") -> None:
        """Load a chunk of Python code.

        :param source_code: python source code
        :param filename: filename associated with the Python code
        """
        code_ast = ast.parse(source_code, filename)
        self.check(code_ast)
        code = compile(code_ast, filename, "exec")
        exec(code, self.mod.__dict__)


class PlanActionEnv(BaseEnv):
    """Store the action environment.

    This includes the build/host/target as well as additional parameters
    coming from the plan.
    """

    action: str
    plan_line: str
    plan_args: Dict[str, Any]
    plan_call_args: Dict[str, Any]
    push_to_store: bool
    default_build: bool
    module: Optional[str]
    source_packages: Optional[List[str]]


class PlanContext:
    """Context in which a Plan is executed."""

    def __init__(
        self,
        stack: Optional[List[PlanActionEnv]] = None,
        plan: Optional[Plan] = None,
        ignore_disabled: bool = True,
        server: Optional[BaseEnv] = None,
        build: Optional[str] = None,
        host: Optional[str] = None,
        target: Optional[str] = None,
        enabled: bool = True,
        default_push_to_store: bool = False,
        **kwargs: Any,
    ):
        """Initialize an execution context or a scope.

        :param stack: stack of PlanAction object that keep track of scopes. Used
            only internally. User instantiation of PlanContext should be done
            with stack set to None.
        :param plan: the plan to execute
        :param ignore_disabled: when true, discard all lines in
            blocks "with defaults(enabled=False):"
        :param server: a BaseEnv object that represent the host default env.
            server parameter is taken into account only during creation of
            the initial context.
        :param build: see e3.env.BaseEnv.set_env
        :param host: see e3.env.BaseEnv.set_env
        :param target: see e3.env.BaseEnv.set_env
        :param enabled: whether the plan line is enabled or disabled
        :param default_push_to_store: whether pushing packages in the package store
            is enabled or not, this is the default value and can be overriden
            by setting push_to_store attribute
        :param kwargs: additional data for the current scope/context
        """
        self.ignore_disabled = ignore_disabled
        if stack:
            assert server is None, "passing server and stack is not supported"
            # This is a scope creation, so copy current env
            self.stack = stack
            self.plan = plan
            new = self.stack[-1].copy(build=build, host=host, target=target)

            if not enabled:
                # we are in a block with enabled=False set, disable all
                # lines in that block
                new.enabled = enabled

        else:
            self.stack = []
            if server is not None:
                # This is a new context
                new = PlanActionEnv.from_env(server)
            else:
                # This is a new context with no server information. In that
                # case retrieve defaults for the local machine.
                new = PlanActionEnv()
                new.set_env(build, host, target)
            new.push_to_store = default_push_to_store
            new.default_build = False
            new.module = None
            new.source_packages = None
            new.enabled = enabled

        # Store additional data
        for k, v in kwargs.items():
            setattr(new, k, v)

        # And push on the stack
        self.stack.append(new)

        # Registered functions that correspond to actions. Note that
        # there is no need to propagate registered action to children
        # scopes. Only initial context use them. The overall scheme
        # works also because all scopes refer to the same stack of env
        # (because the object is mutable).
        self.actions: Dict[str, Callable] = {}
        self.action_list: List[PlanActionEnv] = []

    def register_action(self, name: str, fun: Callable) -> None:
        """Register a function that correspond to an action.

        :param name: name used in the plans
        :param fun: python function. The function itself does
            not require an implementation. Only signature is
            is used
        """
        self.actions[name] = fun

    @property
    def env(self) -> PlanActionEnv:
        """Get environment for current scope.

        :return: the current scope environment
        """
        return self.stack[-1]

    @property
    def default_env(self) -> BaseEnv:
        """Get initial environment.

        :return: the environment set during creation of the
            initial context
        """
        return self.stack[0]

    def execute(
        self, plan: Plan, entry_point_name: str, verify: bool = False
    ) -> List[PlanActionEnv]:
        """Execute a plan.

        :param plan: the plan to execute
        :param entry_point_name: entry point to call in the plan. It can be
            either a function name in the plan or an entry_point function
        :param verify: verify whether the entry point name is a
            electrolyt entry point
        :raise: PlanError
        :return: a list of plan actions
        """
        # Give access to some useful data during plan execution
        plan.mod.__dict__["env"] = self.env
        plan.mod.__dict__["default_env"] = self.default_env

        defaults = partial(PlanContext, self.stack, plan, self.ignore_disabled)
        plan.mod.__dict__["defaults"] = defaults

        for a in self.actions:
            # On each action _add_action will be called with first parameter
            # fixed to the corresponding action name.
            fun = partial(self._add_action, a)
            plan.mod.__dict__[a] = fun

        self.action_list = []
        self.plan = plan

        if entry_point_name in plan.entry_points:
            plan.entry_points[entry_point_name].execute()
        else:
            # ??? An error should be raised as soon as entry points are
            # used everywhere
            plan.mod.__dict__[entry_point_name]()

        return self.action_list

    def _add_action(self, name: str, *args: Any, **kwargs: Any) -> None:
        """Process action calls in plans.

        :param name: action name
        :param args: positional arguments of the action call
        :param kwargs: keyword arguments of the action call
        """
        if self.ignore_disabled and not self.env.enabled:
            return

        if TYPE_CHECKING:
            assert self.plan is not None

        # ??? sometimes to understand the context it would be better to have
        # several lines of plan, e.g. when an action is created by calling
        # a function defined in a plan. Include all these lines separated
        # by ';'. A better fix would be to change plan_line to plan_lines
        # containing a tuple of plan_line.
        plan_line = "unknown filename:unknown lineno"
        # Retrieve the plan line
        try:
            caller_frames = inspect.getouterframes(frame=inspect.currentframe())
            caller_frames_in_plan = []
            for frame in caller_frames:
                frame_filename = frame.filename
                if frame_filename.endswith(self.plan.plan_ext):
                    caller_frames_in_plan.append(frame)
        except Exception:  # defensive code
            # do not crash when inspect frames fails
            pass
        else:
            if not caller_frames_in_plan:
                # No information ?
                pass
            else:
                plan_line = ";".join(
                    f"{caller_frame.filename}:{caller_frame.lineno}"
                    for caller_frame in caller_frames_in_plan
                )

        # First create our initial object based on current scope env
        result = self.env.copy()

        # Process arguments
        call_args = inspect.getcallargs(self.actions[name], *args, **kwargs)

        # Push function arguments into the result object. If an arg value
        # is None then environment is not updated (handling of defaults
        # coming from environment). For the build, host and target arguments
        # a special processing is done to make the corresponding set_env
        # call on the result BaseEnv object
        platform: Dict[str, Optional[str]] = {
            "build": None,
            "host": None,
            "target": None,
        }

        # Likewise board argument is used to change only the machine name
        # of the target. ??? change name ???
        board = None

        for k, v in call_args.items():
            if k in platform:
                platform[k] = v
            elif k == "board":
                board = v
            elif v is not None or not hasattr(result, k):
                setattr(result, k, v)

        # Handle propagation of environment from the context
        if platform["host"] is None and result.is_canadian:
            platform["host"] = "host"
        if platform["target"] is None and result.is_cross:
            platform["target"] = "target"
        if platform["target"] == result.host.platform:
            # ??? This special case is temporary ???
            # the goal is avoid cross from a -> a which are
            # not current supported.
            # Plans should be updated to use target='host'
            # instead of target=env.host.platform
            platform["target"] = "host"

        result.set_env(**platform)

        # If necessary adjust target machine name
        if board is not None:
            result.set_target(
                result.target.platform,
                result.target.os.version,
                board,
                result.target.os.mode,
            )

        # Set action attribute (with action name)
        result.action = name
        result.plan_line = plan_line
        result.plan_args = result.to_dict()
        result.plan_call_args = call_args

        # Push the action in the current list
        self.action_list.append(result)

    def __enter__(self) -> None:
        assert self.plan is not None
        self.plan.mod.__dict__["env"] = self.env
        return None

    def __exit__(
        self,
        _type: Optional[Type[BaseException]],
        _value: Optional[BaseException],
        _tb: Optional[TracebackType],
    ) -> None:
        del _type, _value, _tb
        self.stack.pop()
        assert self.plan is not None
        self.plan.mod.__dict__["env"] = self.env
