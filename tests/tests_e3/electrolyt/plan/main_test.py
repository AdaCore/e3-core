import e3.electrolyt.entry_point as entry_point
import e3.electrolyt.host as host
import e3.electrolyt.plan as plan
import e3.env


def build_action(spec, build=None, host=None, target=None, board=None):
    return "build " + spec


def _get_new_plancontext(machine_name, ignore_disabled=True):
    server = host.Host(hostname=machine_name, platform="x86_64-linux", version="suse11")

    context = plan.PlanContext(server=server, ignore_disabled=ignore_disabled)
    context.register_action("build", build_action)
    return context


def _get_plan(data, content):
    myplan = plan.Plan(data, entry_point_cls={"ms_preset": entry_point.EntryPoint})
    with open("plan.txt", "w") as f:
        f.write("\n".join(content))
    myplan.load("plan.txt")
    return myplan


def test_simple_plan():
    """Test a very basic electrolyt plan."""
    context = _get_new_plancontext("myserver")

    myplan = _get_plan(
        data={"a": "a", "b": "b"},
        content=[
            "def myserver():\n",
            "    build(a)\n",
            '    build(b, build="x86-linux", host="x86-linux",',
            '          target="x86-windows")\n',
        ],
    )

    actions = context.execute(myplan, "myserver")
    assert len(actions) == 2
    assert actions[0].spec == "a"
    assert actions[1].build.platform == "x86-linux"
    assert actions[1].target.platform == "x86-windows"
    assert actions[1].action == "build"
    assert actions[1].spec == "b"


def test_plan_without_server_info():
    context = plan.PlanContext()
    context.register_action("build", build_action)
    myplan = _get_plan(data={"a": "a"}, content=["def myserver():\n", "    build(a)\n"])
    actions = context.execute(myplan, "myserver")
    assert actions[0].build.platform == e3.env.Env().build.platform


def test_plan_scope():
    context = _get_new_plancontext("myserver")

    myplan = _get_plan(
        data={},
        content=[
            "def myserver():\n",
            '    build("foo")\n'
            '    with defaults(build="x86_64-windows",\n'
            '                  host="x86-windows",\n'
            '                  target="x86-linux",\n'
            '                  weathers=["dev"]):\n'
            '        build("foo")\n'
            '        with defaults(target="x86_64-linux"):\n'
            '            build("foo")\n'
            '        with defaults(bar="bar"):\n'
            "            build(env.bar)\n"
            '    build("bar")\n',
        ],
    )

    actions = context.execute(myplan, "myserver")
    assert len(actions) == 5
    assert actions[0].spec == "foo"
    assert actions[0].build.platform == actions[0].target.platform
    assert actions[1].target.platform == "x86-linux"
    assert actions[1].build.platform == "x86_64-windows"
    assert actions[1].host.platform == "x86-windows"
    assert actions[1].weathers == ["dev"]
    assert actions[2].target.platform == "x86_64-linux"
    assert actions[3].spec == "bar"
    assert actions[3].target.platform == "x86-linux"
    assert actions[4].build.platform == actions[0].build.platform
    assert actions[4].build.platform == actions[4].target.platform


def test_board():
    """Test a very basic electrolyt plan."""
    context = _get_new_plancontext("myserver")

    myplan = _get_plan(
        data={"a": "a", "b": "b"},
        content=["def myserver():\n", '    build(a, board="bobby")\n'],
    )

    actions = context.execute(myplan, "myserver")
    assert len(actions) == 1
    assert actions[0].spec == "a"
    assert actions[0].target.machine == "bobby"


def test_entry_points():
    """Test a plan containing electrolyt entry points."""
    plan_content = [
        '@machine(name="machine1", description="Machine 1",',
        '         platform="x86_64-linux", version="rhES6")',
        "def machine1():",
        '    build("a")',
        "",
        '@machine(description="Machine 2",',
        '         platform="x86_64-linux", version="rhES6")',
        "def machine2():",
        '    build("b")',
        "",
        '@ms_preset(name="foo")',
        'def run_foo():    build("c")',
    ]

    myplan = _get_plan({}, plan_content)

    db = myplan.entry_points

    assert len(db) == 3
    assert db["foo"].kind == "ms_preset"
    assert db["foo"].name == "foo"
    assert db["foo"].fun.__name__ == "run_foo"
    assert db["machine1"].description == "Machine 1"
    assert db["machine2"].name == "machine2"

    context = _get_new_plancontext("machine2")
    actions = context.execute(myplan, "machine2")
    assert len(actions) == 1
    assert actions[0].spec == "b"

    ep_executed = [ep for ep in list(db.values()) if ep.executed]

    assert len(ep_executed) == 1
    assert ep_executed[0].name == "machine2"


def test_plan_disable_lines():
    """Check that lines in enabled=False blocks are disabled."""
    context = _get_new_plancontext("myserver")

    myplan = _get_plan(
        data={},
        content=[
            "def myserver():\n",
            '    build("foo")\n'
            "    with defaults(enabled=False):\n"
            '        build("bar1")\n'
            # It is not possible to "revert" the enabled=False status
            "        with defaults(enabled=True):\n"
            '            build("bar2")\n'
            '    build("bar3")\n',
        ],
    )

    actions = context.execute(myplan, "myserver")
    assert len(actions) == 2
    assert actions[0].spec == "foo"
    assert actions[1].spec == "bar3"

    context2 = _get_new_plancontext("myserver", ignore_disabled=False)
    actions2 = context2.execute(myplan, "myserver")
    assert len(actions2) == 4
    assert actions2[0].spec == "foo"
    assert actions2[1].spec == "bar1"
    assert actions2[2].spec == "bar2"
    assert actions2[3].spec == "bar3"


def test_plan_disable_lines_with_conditional_constants():
    """Check that lines in enabled=False blocks are disabled."""
    context = _get_new_plancontext("myserver")

    myplan = _get_plan(
        data={},
        content=[
            "def myserver():\n",
            '    build("foo")\n'
            '    enabled = cond("old", date=lambda x: x.year == 2001)\n'
            "    with defaults(enabled=enabled):\n"
            '        build("bar")\n',
        ],
    )

    actions = context.execute(myplan, "myserver")
    assert len(actions) == 1
    assert actions[0].spec == "foo"

    context2 = _get_new_plancontext("myserver", ignore_disabled=False)
    actions2 = context2.execute(myplan, "myserver")
    assert len(actions2) == 2
    assert actions2[0].spec == "foo"
    assert actions2[1].spec == "bar"

    assert not actions2[1].plan_args["enabled"]
    list(myplan.toggleable_bool_group.shuffle())
    assert actions2[1].plan_args["enabled"]
