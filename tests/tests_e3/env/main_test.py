import sys
import e3.env
import e3.platform


def test_autodetect():
    sys_platform = sys.platform.replace('linux2', 'linux')
    assert sys_platform in str(e3.platform.Platform.get(is_host=True))

    assert sys_platform in e3.env.Env().build.platform

    b = e3.env.BaseEnv()
    b.set_build('x86-linux', 'rhES7')
    assert b.build.platform == 'x86-linux'
    assert sys_platform in e3.env.Env().build.platform

    assert '--build=x86-linux,rhES7' in b.cmd_triplet()

    b.set_host('x86_64-linux', 'rhES7')
    assert '--build=x86-linux,rhES7' in b.cmd_triplet()
    assert '--host=x86_64-linux,rhES7' in b.cmd_triplet()
    assert b.get_attr('build.os.version') == 'rhES7'


def test_store():
    c = e3.env.Env()

    c.abc = 'foo'

    c.store()

    c.abc = 'bar'

    c.restore()

    assert c.abc == 'foo'
