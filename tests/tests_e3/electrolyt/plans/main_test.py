from __future__ import absolute_import, division, print_function

import e3.electrolyt.hosts as host
import e3.electrolyt.plans as plan


def test_simple_plan():

    server = host.Host(hostname='myserver',
                       platform='x86_64-linux',
                       version='suse11')
    context = plan.PlanContext(server=server)

    def build(spec, build=None, host=None, target=None):
        return 'build ' + spec

    myplan = plan.Plan(data={'a': 'a', 'b': 'b'})

    with open('plan.txt', 'w') as f:
        f.write(u'def myserver():\n')
        f.write(u'    build(a)\n')
        f.write(u'    build(b, build="x86-linux", host="x86-linux",')
        f.write(u'          target="x86-windows")\n')

    myplan.load('plan.txt')

    context.register_action('build', build)
    actions = context.execute(myplan, 'myserver')
    assert len(actions) == 2
    assert actions[0].spec == 'a'
    assert actions[1].build.platform == 'x86-linux'
    assert actions[1].target.platform == 'x86-windows'
    assert actions[1].action == 'build'
    assert actions[1].spec == 'b'
