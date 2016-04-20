import e3.fs
import e3.os.fs
import e3.os.process
import os
import pytest
import tempfile
import sys


def test_run_shebang():
    """Verify that the parse shebang option works."""
    tempd = tempfile.mkdtemp(prefix='test_e3_os_process')
    try:
        prog_filename = os.path.join(tempd, 'prog')
        with open(prog_filename, 'wb') as f:
            f.write(b'#!/usr/bin/env python\n')
            f.write(b'print("running python prog")\n')
        e3.os.fs.chmod('a+x', prog_filename)
        p = e3.os.process.Run([prog_filename], parse_shebang=True)
        assert p.out == 'running python prog\n'
    finally:
        e3.fs.rm(tempd, True)


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
        assert 'e3-bin-not-found not found' in err


def test_enable_commands_handler():
    tempd = tempfile.mkdtemp()
    try:
        log_file = os.path.join(tempd, 'cmds.log')
        h = e3.os.process.enable_commands_handler(log_file)
        try:
            e3.os.process.Run([sys.executable, '-c', 'print "dummy"'])
            e3.os.process.Run([sys.executable, '-c', 'print "dummy2"'])
        finally:
            e3.os.process.disable_commands_handler(h)

        with open(log_file, 'rb') as fd:
            lines = fd.read().splitlines()
        assert len(lines) == 2

    finally:
        e3.fs.rm(tempd, True)
