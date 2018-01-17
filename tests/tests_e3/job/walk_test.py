from __future__ import absolute_import, division, print_function

import sys

from e3.anod.status import ReturnValue
from e3.collection.dag import DAG
from e3.job import EmptyJob, Job, ProcessJob
from e3.job.walk import Walk


class DoNothingJob(Job):
    """A Job which inherits Job's implementation of the status attribute."""

    def run(self):
        pass


class ControlledJob(ProcessJob):
    """A ProcessJob for testing purposes.

    The process's behavior is configured by the suffix's UID (see
    the "cmd" line method for more details on this.
    """

    def __init__(self, uid, data, notify_end):
        super(ControlledJob, self).__init__(uid, data, notify_end)
        self.run_count = 0

    def run(self):
        self.run_count += 1
        return super(ControlledJob, self).run()

    @property
    def cmdline(self):
        result = [sys.executable, '-c']
        if self.uid.endswith('bad'):
            result.append('import sys; sys.exit(1)')
        elif self.uid.endswith('notready:once') and self.run_count < 2:
            result.append('import sys; sys.exit(%d)'
                          % ReturnValue.notready.value)
        elif self.uid.endswith('notready:always'):
            result.append('import sys; sys.exit(%d)'
                          % ReturnValue.notready.value)
        else:
            result.append('print("Hello World")')
        return result


class SimpleWalk(Walk):
    def __init__(self, actions):
        # The list of jobs (by UID) that have been requeued.
        self.saved_jobs = {}
        self.requeued = {}
        super(SimpleWalk, self).__init__(actions)

    def request_requeue(self, job):
        """Requeue the job is not already queued once."""
        # First record the number of times we've been asked to requeue
        # that job, and allow requeuing only twice.
        if job.uid not in self.requeued:
            self.requeued[job.uid] = 0
        self.requeued[job.uid] += 1
        return self.requeued[job.uid] < 3

    def create_job(self, uid, data, predecessors, notify_end):
        if uid.endswith('dry-run'):
            # Create a dry-run job, which is a job that never runs
            # (EmptyJob) and returns ReturnValue.success.
            job = EmptyJob(uid, data, notify_end, ReturnValue.success)
        elif uid.endswith('do-nothing'):
            job = DoNothingJob(uid, data, notify_end)
        else:
            job = ControlledJob(uid, data, notify_end)
        self.saved_jobs[job.uid] = job
        return job

    def create_failed_job(self, uid, data, predecessors, reason, notify_end):
        job = super(SimpleWalk, self).create_failed_job(
            uid, data, predecessors, reason, notify_end)
        self.saved_jobs[job.uid] = job
        return job


class TestWalk(object):
    def test_good_job_no_predecessors(self):
        """Simple case of a leaf job."""
        actions = DAG()
        actions.add_vertex('1')
        c = SimpleWalk(actions)

        job = c.saved_jobs['1']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

        assert c.job_status == {'1': ReturnValue.success}
        assert c.requeued == {}

    def test_bad_job_no_predecessors(self):
        """Simple case of a leaf job failing."""
        actions = DAG()
        actions.add_vertex('1.bad')
        c = SimpleWalk(actions)

        job = c.saved_jobs['1.bad']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue(1)
        assert c.job_status == {'1.bad': ReturnValue(1)}
        assert c.requeued == {}

    def test_failed_predecessor(self):
        """Simulate the scenarior when a predecessor failed."""
        actions = DAG()
        actions.add_vertex('1.bad')
        actions.add_vertex('2', predecessors=['1.bad'])
        c = SimpleWalk(actions)

        job = c.saved_jobs['1.bad']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue(1)

        job = c.saved_jobs['2']
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.failure

        assert c.job_status == {'1.bad': ReturnValue(1),
                                '2': ReturnValue.failure}
        assert c.requeued == {}

    def test_job_not_ready_then_ok(self):
        """Rerunning a job that first returned notready."""
        actions = DAG()
        actions.add_vertex('1.notready:once')
        c = SimpleWalk(actions)

        job = c.saved_jobs['1.notready:once']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

        assert c.job_status == {'1.notready:once': ReturnValue.success}
        assert c.requeued == {'1.notready:once': 1}

    def test_job_never_ready(self):
        """Trying to run a job repeatedly returning notready."""
        actions = DAG()
        actions.add_vertex('1.notready:always')
        c = SimpleWalk(actions)

        job = c.saved_jobs['1.notready:always']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.notready

        assert c.job_status == {'1.notready:always': ReturnValue.notready}
        assert c.requeued == {'1.notready:always': 3}

    def test_dry_run(self):
        """Simulate the use actions with "dry run" behavior."""
        actions = DAG()
        actions.add_vertex('1.dry-run')
        actions.add_vertex('2.dry-run', predecessors=['1.dry-run'])
        c = SimpleWalk(actions)

        job = c.saved_jobs['1.dry-run']
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.success

        job = c.saved_jobs['2.dry-run']
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.success

        assert c.job_status == {'1.dry-run': ReturnValue.success,
                                '2.dry-run': ReturnValue.success}
        assert c.requeued == {}

    def test_do_nothing_job(self):
        """Test DAG leading us to create a DoNothingJob object."""
        actions = DAG()
        actions.add_vertex('1.do-nothing')
        actions.add_vertex('2', predecessors=['1.do-nothing'])
        c = SimpleWalk(actions)

        job = c.saved_jobs['1.do-nothing']
        assert isinstance(job, DoNothingJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

        job = c.saved_jobs['2']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

        assert c.job_status == {'1.do-nothing': ReturnValue.success,
                                '2': ReturnValue.success}
        assert c.requeued == {}
