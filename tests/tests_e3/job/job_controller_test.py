from __future__ import absolute_import, division, print_function

import sys

from e3.anod.status import ReturnValue
from e3.collection.dag import DAG
from e3.job import EmptyJob, ProcessJob, StatusBasedJobController


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


class SimpleController(StatusBasedJobController):
    """A Simple controller."""

    def __init__(self, actions):
        super(SimpleController, self).__init__(actions)
        # The list of jobs (by UID) that have been requeued.
        self.requeued = {}

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
            return EmptyJob(uid, data, notify_end, ReturnValue.success)
        else:
            return ControlledJob(uid, data, notify_end)


class TestStatusBasedJobController(object):

    def test_good_job_no_predecessors(self):
        """Simple case of a leaf job."""
        actions = DAG()
        actions.add_vertex('1')
        c = SimpleController(actions)

        job = c.get_job('1', None, [], print)
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        job.run()
        c.collect(job)
        assert c.job_status == {'1': ReturnValue.success}
        assert c.requeued == {}

    def test_bad_job_no_predecessors(self):
        """Simple case of a leaf job failing."""
        actions = DAG()
        actions.add_vertex('1.bad')
        c = SimpleController(actions)

        job = c.get_job('1.bad', None, [], print)
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        job.run()
        requeued = c.collect(job)
        assert not requeued
        assert c.job_status == {'1.bad': ReturnValue(1)}
        assert c.requeued == {}

    def test_failed_predecessor(self):
        """Simulate the scenarior when a predecessor failed."""
        actions = DAG()
        actions.add_vertex('1.bad')
        actions.add_vertex('2', predecessors=['1.bad'])
        c = SimpleController(actions)

        job = c.get_job('1.bad', None, [], print)
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        job.run()
        requeued = c.collect(job)
        assert not requeued
        assert c.job_status == {'1.bad': ReturnValue(1)}
        assert c.requeued == {}

        job = c.get_job('2', None, ['1.bad'], print)
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        job.run()
        requeued = c.collect(job)
        assert not requeued
        assert c.job_status == {'1.bad': ReturnValue(1),
                                '2': ReturnValue.force_skip}
        assert c.requeued == {}

    def test_job_not_ready_then_ok(self):
        """Rerunning a job that first returned notready."""
        actions = DAG()
        actions.add_vertex('1.notready:once')
        c = SimpleController(actions)

        job = c.get_job('1.notready:once', None, [], print)
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        job.run()
        requeued = c.collect(job)
        assert requeued is True
        assert c.job_status == {'1.notready:once': ReturnValue.notready}
        assert c.requeued == {'1.notready:once': 1}

        job.run()
        requeued = c.collect(job)
        assert requeued is False
        assert c.job_status == {'1.notready:once': ReturnValue.success}
        assert c.requeued == {'1.notready:once': 1}

    def test_job_never_ready(self):
        """Trying to run a job repeatedly returning notready."""
        actions = DAG()
        actions.add_vertex('1.notready:always')
        c = SimpleController(actions)

        job = c.get_job('1.notready:always', None, [], print)
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        job.run()
        requeued = c.collect(job)
        assert requeued is True
        assert c.job_status == {'1.notready:always': ReturnValue.notready}
        assert c.requeued == {'1.notready:always': 1}

        # Try running again. We should be getting the same outcome.
        job.run()
        requeued = c.collect(job)
        assert requeued is True
        assert c.job_status == {'1.notready:always': ReturnValue.notready}
        assert c.requeued == {'1.notready:always': 2}

        # Try running again. Still not ready, but no requeuing done
        # anymore.
        job.run()
        requeued = c.collect(job)
        assert requeued is False
        assert c.job_status == {'1.notready:always': ReturnValue.notready}
        assert c.requeued == {'1.notready:always': 3}

    def test_dry_run(self):
        """Simulate the use actions with "dry run" behavior."""
        actions = DAG()
        actions.add_vertex('1.dry-run')
        actions.add_vertex('2.dry-run', predecessors=['1.dry-run'])
        c = SimpleController(actions)

        job = c.get_job('1.dry-run', None, [], print)
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        job.run()
        requeued = c.collect(job)
        assert requeued is False
        assert c.job_status == {'1.dry-run': ReturnValue.success}
        assert c.requeued == {}

        job = c.get_job('2.dry-run', None, [], print)
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        job.run()
        requeued = c.collect(job)
        assert requeued is False
        assert c.job_status == {'1.dry-run': ReturnValue.success,
                                '2.dry-run': ReturnValue.success}
        assert c.requeued == {}
