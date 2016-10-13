from __future__ import absolute_import
import logging
import sys

import e3.collection.dag
import e3.mainloop
import e3.os.process
import e3.os.fs


def run_job(job_data, job_info):
    del job_info
    return e3.os.process.Run(
        [sys.executable, '-c', 'print(%d)' % job_data],
        bg=True)


def new_dag():
    dag = e3.collection.dag.DAG()
    dag.add_vertex(1, 1)
    dag.add_vertex(2, 2)
    dag.add_vertex(3, 3)
    dag.add_vertex(4, 4)
    dag.add_vertex(5, 5, predecessors=[1])
    dag.add_vertex(6, 6, predecessors=[5])
    dag.add_vertex(7, 7, predecessors=[6])
    dag.check()
    return dag


def test_mainloop():
    result = []

    def collect_result(job_data, job_process, job_info):
        del job_data, job_info
        if job_process == e3.mainloop.SKIP_EXECUTION:
            result.append('skip')
        else:
            result.append(int(job_process.out.strip()))

    e3.mainloop.MainLoop(
        [1, 2, 3],
        run_job,
        collect_result,
        parallelism=1)

    result.sort()
    assert result == [1, 2, 3]


def test_mainloop_abort():
    result = []

    # Ask for abort before running the testsuite, we expect
    # all tests aborted.

    def collect_result(job_data, job_process, job_info):
        del job_data, job_info
        if job_process == e3.mainloop.SKIP_EXECUTION:
            result.append('skip')
        else:
            result.append(int(job_process.out.strip()))
    e3.os.fs.touch('abort_file')
    e3.mainloop.MainLoop(
        [4, 5, 6],
        run_job,
        collect_result,
        abort_file='abort_file')
    assert result == ['skip'] * 3

    result = []

    # Now abort after 2 results, first with an abort file
    # and then with a KeyboardInterrupt
    def run_job_and_abort(job_data, job_info):
        del job_info
        if len(result) == 2:
            result.append('abort')
            e3.os.fs.touch('abort_file2')
        return e3.os.process.Run(
            [sys.executable, '-c', 'print(1)'])

    e3.mainloop.MainLoop(
        range(20),
        run_job_and_abort,
        collect_result,
        abort_file='abort_file2',
        parallelism=2)
    assert 1 in result
    assert 'skip' in result
    assert 'abort' in result

    result = []

    def collect_result_interrupt(
            job_data, job_process, job_info):
        logging.debug('get job_data %d', job_data)
        if len(result) == 1:
            result.append('interrupt')
            raise KeyboardInterrupt('mainlooptest')
        elif job_process == e3.mainloop.SKIP_EXECUTION:
            result.append('skip')
        else:
            result.append(int(job_process.out.strip()))

    try:

        e3.mainloop.MainLoop(
            new_dag(),
            run_job,
            collect_result_interrupt,
            parallelism=4)
    except KeyboardInterrupt as e:
        assert 'mainlooptest' in str(e)
    assert 'interrupt' in result
    assert 'skip' in result
    assert 2 in result


def test_mainloop_errors(caplog):
    result = []

    def collect_result_too_many_errors(
            job_data, job_process, job_info):
        if len(result) == 1:
            result.append('error')
            raise e3.mainloop.TooManyErrors
        elif job_process == e3.mainloop.SKIP_EXECUTION:
            result.append('skip')
            # Verify that sending TooManyErrors again is
            # not a problem
        else:
            result.append(int(job_process.out.strip()))

    e3.mainloop.MainLoop(
        new_dag(),
        run_job,
        collect_result_too_many_errors,
        parallelism=0)

    assert 'Too many errors, aborting' in caplog.text
    assert 'error' in result
    assert 'skip' in result
