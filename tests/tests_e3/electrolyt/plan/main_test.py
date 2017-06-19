from __future__ import absolute_import, division, print_function

import e3.electrolyt.host as host
import e3.electrolyt.plan as plan
import e3.env
from e3.electrolyt.entry_point import EntryPointKind

import pytest


def build_action(spec, build=None, host=None, target=None, board=None):
    return 'build ' + spec


def _get_new_plancontext(machine_name):
    server = host.Host(hostname=machine_name,
                       platform='x86_64-linux',
                       version='suse11')

    context = plan.PlanContext(server=server)
    context.register_action('build', build_action)
    return context


def _get_plan(data, content):
    myplan = plan.Plan(data)
    with open('plan.txt', 'w') as f:
        f.write('\n'.join(content))
    myplan.load('plan.txt')
    return myplan


def test_simple_plan():
    """Test a very basic electrolyt plan."""
    context = _get_new_plancontext('myserver')

    myplan = _get_plan(
        data={'a': 'a', 'b': 'b'},
        content=[u'def myserver():\n',
                 u'    build(a)\n',
                 u'    build(b, build="x86-linux", host="x86-linux",',
                 u'          target="x86-windows")\n'])

    actions = context.execute(myplan, 'myserver', verify=False)
    assert len(actions) == 2
    assert actions[0].spec == 'a'
    assert actions[1].build.platform == 'x86-linux'
    assert actions[1].target.platform == 'x86-windows'
    assert actions[1].action == 'build'
    assert actions[1].spec == 'b'


def test_plan_without_server_info():
    context = plan.PlanContext()
    context.register_action('build', build_action)
    myplan = _get_plan(
        data={'a': 'a'},
        content=[u'def myserver():\n',
                 u'    build(a)\n'])
    actions = context.execute(myplan, 'myserver', verify=False)
    assert actions[0].build.platform == e3.env.Env().build.platform


def test_plan_scope():
    context = _get_new_plancontext('myserver')

    myplan = _get_plan(
        data={},
        content=[u'def myserver():\n',
                 u'    build("foo")\n'
                 u'    with defaults(build="x86_64-windows",\n'
                 u'                  host="x86-windows",\n'
                 u'                  target="x86-linux"):\n'
                 u'        build("foo")\n'
                 u'        with defaults(target="x86_64-linux"):\n'
                 u'            build("foo")\n'
                 u'        with defaults(bar="bar"):\n'
                 u'            build(env.bar)\n'
                 u'    build("bar")\n'])

    actions = context.execute(myplan, 'myserver', verify=False)
    assert len(actions) == 5
    assert actions[0].spec == 'foo'
    assert actions[0].build.platform == actions[0].target.platform
    assert actions[1].target.platform == 'x86-linux'
    assert actions[1].build.platform == 'x86_64-windows'
    assert actions[1].host.platform == 'x86-windows'
    assert actions[2].target.platform == 'x86_64-linux'
    assert actions[3].spec == 'bar'
    assert actions[3].target.platform == 'x86-linux'
    assert actions[4].build.platform == actions[0].build.platform
    assert actions[4].build.platform == actions[4].target.platform


def test_board():
    """Test a very basic electrolyt plan."""
    context = _get_new_plancontext('myserver')

    myplan = _get_plan(
        data={'a': 'a', 'b': 'b'},
        content=[u'def myserver():\n',
                 u'    build(a, board="bobby")\n'])

    actions = context.execute(myplan, 'myserver', verify=False)
    assert len(actions) == 1
    assert actions[0].spec == 'a'
    assert actions[0].target.machine == 'bobby'


def test_entry_points():
    """Test a plan containing electrolyt entry points."""
    plan_content = [
        '@machine(name="machine1", description="Machine 1")',
        'def machine1():',
        '    build("a")',
        '',
        '@machine(name="machine2", description="Machine 2")',
        'def machine2():',
        '    build("b")',
        '',
        '@ms_preset(name="foo")',
        'def run_foo():'
        '    build("c")']

    myplan = _get_plan({}, plan_content)

    db = myplan.entry_points

    assert len(db) == 3
    assert db['foo'].name == 'foo'
    assert db['foo'].is_entry_point
    assert db['foo'].kind == EntryPointKind.ms_preset
    assert db['foo'].__name__ == 'run_foo'
    assert db['machine1'].description == 'Machine 1'
    assert db['machine2'].name == 'machine2'
    assert db['machine2'].kind == EntryPointKind.machine

    context = _get_new_plancontext('machine2')
    actions = context.execute(myplan, 'machine2', verify=True)
    assert len(actions) == 1
    assert actions[0].spec == 'b'

    ep_executed = [ep for ep in db.values() if ep.executed]

    assert len(ep_executed) == 1
    assert ep_executed[0].name == 'machine2'


def test_verify_entry_point():
    """PlanContext with verify=True should reject non entry points."""
    plan_context = ['def foo():', '    build("o")']

    my_plan = _get_plan({}, plan_context)
    context = _get_new_plancontext('foo')
    actions = context.execute(my_plan, 'foo')
    assert len(actions) == 1

    with pytest.raises(plan.PlanError) as plan_err:
        context.execute(my_plan, 'foo', verify=True)

    assert 'foo is not an entry point' in str(plan_err)
