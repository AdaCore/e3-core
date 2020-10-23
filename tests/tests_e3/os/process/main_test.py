import os
import sys
import textwrap
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
    prog_filename = os.path.join(os.getcwd(), "prog")
    with open(prog_filename, "wb") as f:
        f.write(b"#!/usr/bin/env python\n")
        f.write(b"import sys\n")
        f.write(b'print("running %s" % sys.argv[1])\n')
    e3.os.fs.chmod("a+x", prog_filename)
    p = e3.os.process.Run([prog_filename, "atest"], parse_shebang=True)
    assert p.out.replace("\r", "") == "running atest\n"

    # Create a shebang spawning a file that does not exist
    with open(prog_filename, "wb") as f:
        f.write(b"#!doesnot exist\n")
        f.write(b'print("running python prog")\n')

    e3.os.fs.chmod("a+x", prog_filename)
    with pytest.raises(OSError) as err:
        e3.os.process.Run([prog_filename], parse_shebang=True)
    assert "doesnot" in str(err)
    assert "doesnot exist" in caplog.text


def test_split_err_out():
    """Split err and out to distinct pipes."""
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('stdout'); sys.stderr.write('stderr')",
        ],
        output=e3.os.process.PIPE,
        error=e3.os.process.PIPE,
    )
    assert p.out == "stdout"
    assert p.err == "stderr"


def test_non_utf8_out():
    """Test that we can get an output for a process not emitting utf-8."""
    p = e3.os.process.Run(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\xff\\xff')"]
    )
    assert p.out == "\\xff\\xff"


def test_rlimit():
    """rlimit kill the child process after a timeout."""

    def run_test():
        p = e3.os.process.Run(
            [
                sys.executable,
                "-c",
                "print('hello'); import sys; sys.stdout.flush(); "
                "import time; time.sleep(10); print('world')",
            ],
            timeout=1,
        )
        assert "hello" in p.out
        assert "world" not in p.out

    run_test()
    if sys.platform == "win32":
        # On Windows make sure that rlimit works when
        # setting the build environment to 64bit windows
        e = e3.env.Env()
        e.store()
        e.set_build("x86_64-windows")
        run_test()
        e.set_build("x86_64-windows64")
        run_test()
        e.restore()


def test_not_found():
    with pytest.raises(OSError) as err:
        e3.os.process.Run(["e3-bin-not-found"])
    assert "e3-bin-not-found not found" in str(err.value)

    with pytest.raises(OSError) as err:
        e3.os.process.Run(["e3-bin-not-found"], parse_shebang=True)
    assert "e3-bin-not-found not found" in str(err.value)

    with pytest.raises(OSError) as err:
        e3.os.process.Run(
            [
                [
                    sys.executable,
                    "-c",
                    'print("a "); import time; time.sleep(10); print("test")',
                ],
                ["e3-bin-not-found2"],
            ]
        )
    assert "e3-bin-not-found2 not found" in str(err.value)


def test_enable_commands_handler():
    log_file = "cmds.log"
    h = e3.os.process.enable_commands_handler(log_file)
    try:
        e3.os.process.Run([sys.executable, "-c", 'print("dummy")'])
        e3.os.process.Run([sys.executable, "-c", 'print("dummy2")'])
    finally:
        e3.os.process.disable_commands_handler(h)

    with open(log_file, "rb") as fd:
        lines = fd.readlines()
    assert len(lines) == 2


@pytest.mark.xfail(sys.platform != "win32", reason="unix implem not complete")
def test_wait_for_processes():
    for v in (1, 2):
        with open("p%d.py" % v, "w") as f:
            f.write(
                "import os\n"
                "while True:\n"
                '    if os.path.exists("end%d"): break\n'
                'print("process%d")\n' % (v, v)
            )

    p1 = e3.os.process.Run([sys.executable, "p1.py"], bg=True)
    p2 = e3.os.process.Run([sys.executable, "p2.py"], bg=True)

    process_list = [p1, p2]
    p3 = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "from e3.os.fs import touch;"
            "from time import sleep;"
            "sleep(0.2);"
            'touch("end1");'
            "sleep(0.2);"
            'touch("end2")',
        ],
        bg=True,
    )
    for _ in range(2):
        result = e3.os.process.wait_for_processes(process_list, 2)
        if result is not None:
            del process_list[result]
    assert len(process_list) == 0

    assert p1.status == 0
    assert p1.out.strip() == "process1"
    assert p2.status == 0
    assert p2.out.strip() == "process2"

    p3.wait()

    assert e3.os.process.wait_for_processes([], 10) is None


def test_run_pipe():
    cmd_left = [sys.executable, "-c", 'print("dummy")']
    cmd_right = [
        sys.executable,
        "-c",
        'import sys; print(sys.stdin.read().replace("y", "ies"))',
    ]
    p = e3.os.process.Run([cmd_left, cmd_right])
    assert p.status == 0
    assert p.out.strip() == "dummies"

    with open("dummy", "w") as f:
        f.write("dummy")
    p = e3.os.process.Run(cmd_right, input="dummy")
    assert p.status == 0
    assert p.out.strip() == "dummies"


def test_command_line_image():
    result = e3.os.process.command_line_image(["echo", ""])
    assert result == "echo ''"
    result = e3.os.process.command_line_image([["echo", "dummy"], ["grep", "m"]])
    assert result == "echo dummy | grep m"


def test_poll():
    result = e3.os.process.Run(
        [sys.executable, "-c", 'import time; time.sleep(1); print("process")'], bg=True
    )

    assert result.poll() is None
    time.sleep(2)
    assert result.poll() == 0
    assert result.out.strip() == "process"

    # check that subsequent calls to poll or wait do not crash or alter the
    # result
    assert result.poll() == 0
    assert result.wait() == 0
    assert result.out.strip() == "process"


def test_file_redirection():
    p_out = "p.out"
    result = e3.os.process.Run(
        [sys.executable, "-c", 'print("dummy")'],
        input=None,
        output=p_out,
        error=e3.os.process.STDOUT,
    )
    with open(p_out) as fd:
        content = fd.read().strip()
    assert result.status == 0
    assert content == "dummy"


def test_output_append():
    p_out = "p.out"
    e3.os.process.Run([sys.executable, "-c", 'print("line1")'], output=p_out)
    e3.os.process.Run([sys.executable, "-c", 'print("line2")'], output="+" + p_out)
    with open(p_out) as fd:
        content = fd.read().strip()
    assert content == "line1\nline2"


def test_pipe_input():
    p = e3.os.process.Run(
        [sys.executable, "-c", "import sys; print(sys.stdin.read())"], input="|dummy"
    )
    assert p.out.strip() == "dummy"


def test_is_running():
    p = e3.os.process.Run([sys.executable, "-c", "import time; time.sleep(1)"], bg=True)
    assert e3.os.process.is_running(p.pid)
    p.kill(recursive=False)

    # On windows we don't want to wait as otherwise pid will be reused
    # Note also that the semantic is slightly different between Unix
    # and Windows. is_running will report false on Windows once the
    # process is in a waitable state.
    if sys.platform != "win32":
        p.wait()
    assert not e3.os.process.is_running(p.pid)

    p.wait()


@pytest.mark.skipif(psutil is None, reason="require psutil")
def test_is_running_non_existant():
    """Call is_running on non-existing process."""
    pid_list = psutil.pids()
    pid_list.sort()

    # Try to found a non existing process
    for a in range(1, 1000):
        running = e3.os.process.is_running(pid_list[-1] + a)
        if not running:
            break
    assert not running, "could not find non existing process"


@pytest.mark.xfail(reason="unstable test, p.status can be 0")
def test_interrupt():
    t0 = time.time()
    p = e3.os.process.Run(
        [sys.executable, "-c", "import time; time.sleep(30)"], bg=True
    )
    time.sleep(0.5)  # Make sure the process had the time to start
    p.interrupt()
    t1 = time.time()
    assert t1 - t0 < 2, "process not interrupted after 2s?"

    p.wait()
    assert p.status != 0


@pytest.mark.skipif(psutil is None, reason="require psutil")
def test_kill_process_tree():
    is_appveyor_test = bool(os.environ.get("APPVEYOR"))
    wait_timeout = 3
    if is_appveyor_test:
        wait_timeout *= 3
    p1 = e3.os.process.Run(
        [sys.executable, "-c", "import time; time.sleep(10); import sys; sys.exit(2)"],
        bg=True,
    )
    e3.os.process.kill_process_tree(p1.pid, timeout=wait_timeout)
    assert p1.status != 2
    assert not p1.is_running()

    time.sleep(2.0)

    def get_one_child(idx):
        pid_file = f"child_pid_{idx}"
        gen_prog_name = f"child_prog_{idx}"
        prog = textwrap.dedent(
            f"""\
            import e3.os.process, os, sys, time
            child_cmd = "import os, time;"
            child_cmd += "f = open('{pid_file}', 'w');"
            child_cmd += "f.write(str(os.getpid()));"
            child_cmd += "f.close();"
            child_cmd += "time.sleep(60);"
            e3.os.process.Run([sys.executable, '-c', child_cmd])
            time.sleep(60)
            """
        )

        with open(gen_prog_name, "w") as f:
            f.write(prog)

        parent_process = e3.os.process.Run([sys.executable, gen_prog_name], bg=True)
        for _ in range(0, 100):
            try:
                with open(pid_file) as f:
                    child_pid = f.read()
                    if child_pid:
                        break
            except OSError:
                pass

            time.sleep(0.1)
        child_pid = int(child_pid)
        e3.fs.rm(gen_prog_name)
        e3.fs.rm(pid_file)
        child_process = psutil.Process(child_pid)

        # Make sure that the child process is indeed a child of parent_process
        for proc in psutil.Process(parent_process.pid).children(recursive=True):
            if proc.pid == child_pid:
                break
        else:
            raise AssertionError("issue when trying to get child process")
        return parent_process, child_process

    p2, p2_child = get_one_child(1)
    e3.os.process.kill_process_tree(p2.pid, timeout=wait_timeout)

    assert not p2.is_running()
    assert not p2_child.is_running()

    p3, p3_child = get_one_child(2)
    p3.kill(timeout=wait_timeout)

    assert not p3.is_running()
    assert not p3_child.is_running()

    # killing it more than once should also work
    assert e3.os.process.kill_process_tree(p3.pid) is True
    assert e3.os.process.kill_process_tree(p3.internal) is True


def test_run_with_env():
    os.environ["EXT_VAR"] = "bar"
    cmd = (
        [
            sys.executable,
            "-c",
            'import os; print(os.environ.get("TEST_RUN_VAR")'
            ' + os.environ.get("EXT_VAR", "world"))',
        ],
    )
    p1 = e3.os.process.Run(cmd, env={"TEST_RUN_VAR": "foo"}, ignore_environ=False)
    assert p1.out.strip() == "foobar"

    p1 = e3.os.process.Run(cmd, env={"TEST_RUN_VAR": "hello"}, ignore_environ=True)
    assert p1.out.strip() == "helloworld"


def test_no_rlimit(caplog):
    fake_rlimit = e3.os.process.get_rlimit(platform="null")
    old_get_rlimit = e3.os.process.get_rlimit
    e3.os.process.get_rlimit = lambda: fake_rlimit  # type: ignore

    try:
        p1 = e3.os.process.Run([sys.executable, "-c", "print(1)"], timeout=2)
        assert p1.out.strip() == "1"
        assert "cannot find rlimit" in caplog.text
    finally:
        e3.os.process.get_rlimit = old_get_rlimit


@pytest.mark.skipif(sys.platform != "win32", reason="windows specific test")
def test_shell_override():
    """Unix shell shebang handling.

    On windows we ensure that /bin/bash /bin/sh shebangs are replaced by
    SHELL env var.
    """
    work_dir = os.getcwd()
    os.environ["SHELL"] = sys.executable
    test_file_path = os.path.join(work_dir, "shebang_test.sh")
    with open(test_file_path, "w") as fd:
        fd.write("#!/bin/bash\nimport sys; print(sys.executable)\n")
    p = e3.os.process.Run([test_file_path], parse_shebang=True)
    assert p.out.strip() == sys.executable
