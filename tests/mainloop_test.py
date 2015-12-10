import sys

import e3.mainloop
import e3.os.process


def test_mainloop():

    result = []

    def run_job(job_data, job_info):
        return e3.os.process.Run(
            [sys.executable, '-c', 'print %s' % str(job_data)],
            bg=True)

    def collect_result(job_data, job_process, job_info):
        result.append(job_process.out.strip())

    e3.mainloop.MainLoop(
        [1, 2, 3],
        run_job,
        collect_result,
        parallelism=1)

    assert result == ['1', '2', '3']


