from __future__ import absolute_import, division, print_function

import os
import sys
import time

import e3.fs
import e3.os.fs
import e3.os.process

import pytest

try:
    import psutil
except ImportError:
    psutil = None


def test_run_shebang(caplog):
    """Verify that the parse shebang option works."""
    prog_filename = os.path.join(os.getcwd(), 'prog')
    with open(prog_filename, 'wb') as f:
        f.write(b'#!/usr/bin/env python\n')
        f.write(b'import sys\n')
        f.write(b'print("running %s" % sys.argv[1])\n')
    e3.os.fs.chmod('a+x', prog_filename)
    p = e3.os.process.Run([prog_filename, 'atest'], parse_shebang=True)
    assert p.out == 'running atest\n'

    # Create a shebang spawning a file that does not exist
    with open(prog_filename, 'wb') as f:
        f.write(b'#!doesnot exist\n')
        f.write(b'print("running python prog")\n')

    e3.os.fs.chmod('a+x', prog_filename)
    with pytest.raises(OSError) as err:
        e3.os.process.Run([prog_filename], parse_shebang=True)
    assert 'doesnot' in str(err)
    assert 'doesnot exist' in caplog.text


def test_rlimit():
    """rlimit kill the child process after a timeout."""
    p = e3.os.process.Run(
        [sys.executable, '-c',
         "print('hello'); import sys; sys.stdout.flush(); "
         "import time; time.sleep(10); print('world')"],
        timeout=1)
    assert 'hello' in p.out
    assert 'world' not in p.out


def test_not_found():
    with pytest.raises(OSError) as err:
        e3.os.process.Run(['e3-bin-not-found'])
    assert 'e3-bin-not-found not found' in str(err.value)

    with pytest.raises(OSError) as err:
        e3.os.process.Run(['e3-bin-not-found'], parse_shebang=True)
    assert 'e3-bin-not-found not found' in str(err.value)

    with pytest.raises(OSError) as err:
        e3.os.process.Run([
            [sys.executable, '-c',
             'print("a "); import time; time.sleep(10); print("test")'],
            ['e3-bin-not-found2']])
    assert 'e3-bin-not-found2 not found' in str(err.value)


def test_enable_commands_handler():
    log_file = 'cmds.log'
    h = e3.os.process.enable_commands_handler(log_file)
    try:
        e3.os.process.Run([sys.executable, '-c', 'print("dummy")'])
        e3.os.process.Run([sys.executable, '-c', 'print("dummy2")'])
    finally:
        e3.os.process.disable_commands_handler(h)

    with open(log_file, 'rb') as fd:
        lines = fd.readlines()
    assert len(lines) == 2


@pytest.mark.xfailif(sys.platform != 'win32',
                     reason="unix implem not complete")
def test_wait_for_processes():
    for v in (1, 2):
        with open('p%d.py' % v, 'w') as f:
            f.write('import os\n'
                    'while True:\n'
                    '    if os.path.exists("end%d"): break\n'
                    'print("process%d")\n' % (v, v))

    p1 = e3.os.process.Run([sys.executable, 'p1.py'], bg=True)
    p2 = e3.os.process.Run([sys.executable, 'p2.py'], bg=True)

    process_list = [p2]
    p3 = e3.os.process.Run(
        [sys.executable, '-c',
         'from e3.os.fs import touch;'
         'from time import sleep;'
         'sleep(0.2);'
         'touch("end1");'
         'sleep(0.2);'
         'touch("end2")'], bg=True)
    result = e3.os.process.wait_for_processes(process_list, 2)
    del process_list[result]
    process_list = [p1, p2]
    e3.os.process.wait_for_processes(process_list, 2)

    assert p1.status == 0
    assert p1.out.strip() == 'process1'
    assert p2.status == 0
    assert p2.out.strip() == 'process2'

    p3.wait()

    assert e3.os.process.wait_for_processes([], 10) is None


def test_run_pipe():
    cmd_left = [sys.executable, '-c', 'print("dummy")']
    cmd_right = [sys.executable, '-c',
                 'import sys; print(sys.stdin.read().replace("y", "ies"))']
    p = e3.os.process.Run([cmd_left, cmd_right])
    assert p.status == 0
    assert p.out.strip() == 'dummies'

    with open('dummy', 'w') as f:
        f.write('dummy')
    p = e3.os.process.Run(cmd_right, input='dummy')
    assert p.status == 0
    assert p.out.strip() == 'dummies'


def test_command_line_image():
    result = e3.os.process.command_line_image(["echo", ""])
    assert result == "echo ''"
    result = e3.os.process.command_line_image([["echo", "dummy"],
                                               ["grep", "m"]])
    assert result == "echo dummy | grep m"


def test_poll():
    import time
    result = e3.os.process.Run(
        [sys.executable, '-c',
         'import time; time.sleep(1); print("process")'], bg=True)

    assert result.poll() is None
    time.sleep(2)
    assert result.poll() == 0
    assert result.out.strip() == 'process'

    # check that subsequent calls to poll or wait do not crash or alter the
    # result
    assert result.poll() == 0
    assert result.wait() == 0
    assert result.out.strip() == 'process'


def test_file_redirection():
    p_out = 'p.out'
    result = e3.os.process.Run(
        [sys.executable, '-c', 'print("dummy")'],
        input=None,
        output=p_out,
        error=e3.os.process.STDOUT)
    with open(p_out) as fd:
        content = fd.read().strip()
    assert result.status == 0
    assert content == 'dummy'


def test_output_append():
    p_out = 'p.out'
    e3.os.process.Run([sys.executable, '-c', 'print("line1")'],
                      output=p_out)
    e3.os.process.Run([sys.executable, '-c', 'print("line2")'],
                      output="+" + p_out)
    with open(p_out, 'r') as fd:
        content = fd.read().strip()
    assert content == "line1\nline2"


def test_pipe_input():
    p = e3.os.process.Run([sys.executable,
                           '-c',
                           'import sys; print(sys.stdin.read())'],
                          input='|dummy')
    assert p.out.strip() == 'dummy'


def test_is_running():
    p = e3.os.process.Run([sys.executable,
                           '-c',
                           'import time; time.sleep(1)'],
                          bg=True)
    assert e3.os.process.is_running(p.pid)
    p.kill(recursive=False)

    # On windows we don't want to wait as otherwise pid will be reused
    # Note also that the semantic is slightly different between Unix
    # and Windows. is_running will report false on Windows once the
    # process is in a waitable state.
    if sys.platform != 'win32':
        p.wait()
    assert not e3.os.process.is_running(p.pid)

    p.wait()


@pytest.mark.xfail(e3.env.Env().build.os.name == 'solaris',
                   reason='known issue: p.status == 0 on Solaris')
def test_interrupt():
    t0 = time.time()
    p = e3.os.process.Run([sys.executable,
                           '-c',
                           'import time; time.sleep(30)'],
                          bg=True)
    p.interrupt()
    t1 = time.time()
    assert t1 - t0 < 2, 'process not interrupted after 2s?'

    p.wait()
    assert p.status != 0


@pytest.mark.skipif(psutil is None, reason='require psutil')
def test_kill_process_tree():
    p1 = e3.os.process.Run(
        [sys.executable, '-c',
         'import time; time.sleep(10); import sys; sys.exit(2)'],
        bg=True)
    e3.os.process.kill_process_tree(p1.pid)
    p1.wait()
    assert p1.status != 2

    def get_one_child():
        cmd = [sys.executable, '-c',
               'import e3.os.process; import time; import sys;'
               ' e3.os.process.Run([sys.executable, "-c",'
               ' "import time; time.sleep(10)"]);'
               'time.sleep(10)']

        p_one_child = e3.os.process.Run(cmd, bg=True)
        for k in range(0, 100):
            p_one_child_children = p_one_child.children()
            if len(p_one_child_children) == 1:
                break
            time.sleep(0.1)
        assert len(p_one_child_children) == 1
        return p_one_child, p_one_child_children

    p2, p2_children = get_one_child()
    e3.os.process.kill_process_tree(p2.pid)
    p2.wait()

    assert not p1.is_running()
    assert not p2.is_running()
    for p in p2_children:
        assert not p.is_running()

    p3, p3_children = get_one_child()
    p3.kill()
    p3.wait()
    assert not p3.is_running()
    for p in p3_children:
        assert not p.is_running()

    # killing it twice should also work
    assert e3.os.process.kill_process_tree(p3.pid) is True


def test_run_with_env():
    os.environ['EXT_VAR'] = 'bar'
    cmd = [
        sys.executable, '-c',
        'import os; print(os.environ.get("TEST_RUN_VAR")'
        ' + os.environ.get("EXT_VAR", "world"))'],
    p1 = e3.os.process.Run(
        cmd,
        env={'TEST_RUN_VAR': 'foo'},
        ignore_environ=False)
    assert p1.out.strip() == 'foobar'

    p1 = e3.os.process.Run(
        cmd,
        env={'TEST_RUN_VAR': 'hello'},
        ignore_environ=True)
    assert p1.out.strip() == 'helloworld'


def test_no_rlimit(caplog):
    fake_rlimit = e3.os.process.get_rlimit(platform='null')
    old_get_rlimit = e3.os.process.get_rlimit
    e3.os.process.get_rlimit = lambda: fake_rlimit

    try:
        p1 = e3.os.process.Run([sys.executable, '-c', 'print(1)'], timeout=2)
        assert p1.out.strip() == '1'
        assert 'cannot find rlimit' in caplog.text
    finally:
        e3.os.process.get_rlimit = old_get_rlimit
