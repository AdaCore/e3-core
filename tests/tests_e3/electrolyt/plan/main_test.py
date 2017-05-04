from __future__ import absolute_import, division, print_function

import e3.electrolyt.host as host
import e3.electrolyt.plan as plan


def _get_new_plancontext(machine_name):
    server = host.Host(hostname=machine_name,
                       platform='x86_64-linux',
                       version='suse11')

    def build(spec, build=None, host=None, target=None):
        return 'build ' + spec

    context = plan.PlanContext(server=server)
    context.register_action('build', build)
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

    actions = context.execute(myplan, 'myserver')
    assert len(actions) == 2
    assert actions[0].spec == 'a'
    assert actions[1].build.platform == 'x86-linux'
    assert actions[1].target.platform == 'x86-windows'
    assert actions[1].action == 'build'
    assert actions[1].spec == 'b'
