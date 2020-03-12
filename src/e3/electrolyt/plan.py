import ast
import imp
import inspect
from functools import partial

from e3.electrolyt.entry_point import Machine, entry_point
from e3.env import BaseEnv
from e3.error import E3Error


class PlanError(E3Error):
    """Error when parsing or executing the plan."""

    pass


class Plan(object):
    """Electrolyt Plan.

    :ivar entry_points: list of entry points found in the plans
    :vartype entry_points: dict
    """

    def __init__(self, data, entry_point_cls=None, plan_ext=".plan"):
        """Initialize a new plan.

        :param data: a dictionary defining additional globals to push
            into plan associated module
        :type data: dict[str, T]
        :param entry_point_cls: dict associating a list of decorator name
            with an entry point class
        :type entry_point_cls: dict[str, T]
        :param plan_ext: plan extension, by default ".plan". This is used to
            detect whether a specific frame is in a plan or in our code. See
            PlanContext._add_action
        :type plan_ext: str
        """
        self.mod = imp.new_module("_anod_plan_")

        # Some additional user symbols
        for k, v in data.items():
            self.mod.__dict__[k] = v

        self.entry_points = {}

        if entry_point_cls is None:
            entry_point_cls = {}

        self.plan_ext = plan_ext

        self.mod.__dict__["machine"] = partial(
            entry_point, self.entry_points, Machine, "machine"
        )

        for name, cls in entry_point_cls.items():
            self.mod.__dict__[name] = partial(entry_point, self.entry_points, cls, name)

    def load(self, filename):
        """Load python code from file.

        :param filename: path to the python code
        :type filename: str
        """
        with open(filename, "rb") as fd:
            source_code = fd.read()
        self.load_chunk(source_code, filename)

    def check(self, code_ast):
        """Check plan coding style."""
        del self, code_ast

    def load_chunk(self, source_code, filename="<unknown>"):
        """Load a chunk of Python code.

        :param source_code: python source code
        :type source_code: str
        :param filename: filename associated with the Python code
        :type filename: str
        """
        code_ast = ast.parse(source_code, filename)
        self.check(code_ast)
        code = compile(code_ast, filename, "exec")
        exec(code, self.mod.__dict__)


class PlanContext(object):
    """Context in which a Plan is executed."""

    def __init__(
        self,
        stack=None,
        plan=None,
        ignore_disabled=True,
        server=None,
        build=None,
        host=None,
        target=None,
        enabled=True,
        **kwargs
    ):
        """Initialize an execution context or a scope.

        :param stack: stack of BaseEnv object that keep track of scopes. Used
            only internally. User instantiation of PlanContext should be done
            with stack set to None.
        :type stack: list[BaseEnv]
        :param plan: the plan to execute
        :type plan: Plan
        :param ignore_disabled: when true, discard all lines in
            blocks "with defaults(enabled=False):"
        :type ignore_disabled: bool
        :param server: a BaseEnv object that represent the host default env.
            server parameter is taken into account only during creation of
            the initial context.
        :type server: BaseEnv
        :param build: see e3.env.BaseEnv.set_env
        :type build: str | None
        :param host: see e3.env.BaseEnv.set_env
        :type host: str | None
        :param target: see e3.env.BaseEnv.set_env
        :type target: str | None
        :param enabled: whether the plan line is enabled or disabled
        :type enabled: bool
        :param kwargs: additional data for the current scope/context
        :type kwargs: dict
        """
        self.ignore_disabled = ignore_disabled
        if stack:
            # This is a scope creation, so copy current env
            self.stack = stack
            self.plan = plan
            new = self.stack[-1].copy(build=build, host=host, target=target)

            if new.enabled and not enabled:
                # we are in a block with enabled=False set, disable all
                # lines in that block
                new.enabled = enabled

        else:
            self.stack = []
            if server is not None:
                # This is a new context
                new = server.copy(build, host, target)
            else:
                # This is a new context with no server information. In that
                # case retrieve defaults for the local machine.
                new = BaseEnv()
                new.set_env(build, host, target)
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
        self.actions = {}
        self.action_list = []

    def register_action(self, name, fun):
        """Register a function that correspond to an action.

        :param name: name used in the plans
        :type name: str
        :param fun: python function. The function itself does
            not require an implementation. Only signature is
            is used
        :type fun: callable
        """
        self.actions[name] = fun

    @property
    def env(self):
        """Get environment for current scope.

        :return: the current scope environment
        :rtype: BaseEnv
        """
        return self.stack[-1]

    @property
    def default_env(self):
        """Get initial environment.

        :return: the environment set during creation of the
            initial context
        :rtype: BaseEnv
        """
        return self.stack[0]

    def execute(self, plan, entry_point_name, verify=False):
        """Execute a plan.

        :param plan: the plan to execute
        :type plan: Plan
        :param entry_point_name: entry point to call in the plan. It can be
            either a function name in the plan or an entry_point function
        :type entry_point_name: str | fun
        :param verify: verify whether the entry point name is a
            electrolyt entry point
        :type verify: bool
        :raise: PlanError
        :return: a list of plan actions
        :rtype: list[callable]
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

    def _add_action(self, name, *args, **kwargs):
        """Process action calls in plans.

        :param name: action name
        :type name: str
        :param args: positional arguments of the action call
        :type args: list
        :param kwargs: keyword arguments of the action call
        :type kwargs: dict
        """
        if self.ignore_disabled and not self.env.enabled:
            return

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
                    (
                        "{}:{}".format(caller_frame.filename, caller_frame.lineno)
                        for caller_frame in caller_frames_in_plan
                    )
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
        platform = {"build": None, "host": None, "target": None}

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

    def __enter__(self):
        self.plan.mod.__dict__["env"] = self.env
        return None

    def __exit__(self, _type, _value, _tb):
        del _type, _value, _tb
        self.stack.pop()
        self.plan.mod.__dict__["env"] = self.env
