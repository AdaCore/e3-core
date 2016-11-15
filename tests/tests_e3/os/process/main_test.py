from __future__ import absolute_import
import e3.fs
import e3.os.fs
import e3.os.process
import os
import pytest
import sys
import time


def test_run_shebang():
    """Verify that the parse shebang option works."""
    prog_filename = os.path.join(os.getcwd(), 'prog')
    with open(prog_filename, 'wb') as f:
        f.write(b'#!/usr/bin/env python\n')
        f.write(b'print("running python prog")\n')
    e3.os.fs.chmod('a+x', prog_filename)
    p = e3.os.process.Run([prog_filename], parse_shebang=True)
    assert p.out == 'running python prog\n'


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


def test_run_pipe():
    p = e3.os.process.Run(
        [[sys.executable, '-c', 'print("dummy")'],
         [sys.executable, '-c',
          'import sys; print(sys.stdin.read().replace("y", "ies"))']])
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
    time.sleep(2)

    # On windows we don't want to wait as otherwise pid will be reused
    # Note also that the semantic is slightly different between Unix
    # and Windows. is_running will report false on Windows once the
    # process is in a waitable state.
    if sys.platform != 'win32':
        p.wait()
    assert not e3.os.process.is_running(p.pid)

    p.wait()
    assert p.status == 0


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


def test_kill_process_tree():
    p1 = e3.os.process.Run(
        [sys.executable, '-c',
         'import time; time.sleep(10); import sys; sys.exit(2)'],
        bg=True)
    e3.os.process.kill_process_tree(p1.pid)
    p1.wait()
    assert p1.status != 2

    p2 = e3.os.process.Run(
        [sys.executable, '-c',
         'import e3.os.process; import time; import sys;'
         ' e3.os.process.Run([sys.executable, "-c",'
         ' "import time; time.sleep(10)"]);'
         'time.sleep(10)'],
        bg=True)
    time.sleep(1)
    p2_children = p2.children()
    assert len(p2_children) == 1
    e3.os.process.kill_process_tree(p2.pid)
    p2.wait()

    assert not p1.is_running()
    assert not p2.is_running()
    for p in p2_children:
        assert not p.is_running()
