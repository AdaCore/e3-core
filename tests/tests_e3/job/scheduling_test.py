import sys

from e3.collection.dag import DAG
from e3.job import Job, ProcessJob
from e3.job.scheduler import Scheduler

import pytest


class NopJob(Job):
    def run(self):
        pass

    @property
    def priority(self):
        try:
            result = -int(self.uid)
        except Exception:
            result = 0
        return result


class SleepJob(ProcessJob):
    @property
    def cmdline(self):
        return [sys.executable, "-c", "import time; time.sleep(6.0)"]


class TestScheduler(object):
    def test_minimal_run(self):
        """Test with only two independent jobs."""
        dag = DAG()
        dag.add_vertex("1")
        dag.add_vertex("2")
        s = Scheduler(Scheduler.simple_provider(NopJob), tokens=2)
        s.run(dag)
        assert s.max_active_jobs == 2

    def test_ordering(self):
        """Test that jobs are ordered correctly."""
        results = []

        def collect(job):
            results.append(job.uid)

        dag = DAG()
        dag.add_vertex("3")
        dag.add_vertex("0")
        dag.add_vertex("1")
        s = Scheduler(Scheduler.simple_provider(NopJob), tokens=1, collect=collect)
        s.run(dag)
        assert tuple(results) == ("0", "1", "3")

    def test_minimal_run2(self):
        """Test with two interdependent jobs."""
        dag = DAG()
        dag.add_vertex("1")
        dag.add_vertex("2", predecessors=["1"])
        s = Scheduler(Scheduler.simple_provider(NopJob), tokens=2)
        s.run(dag)
        assert s.max_active_jobs == 1

    def test_requeue(self):
        """Requeue test.

        Same as previous example except that all tests are requeued
        once.
        """
        results = {}

        def collect(job):
            if job.uid not in results:
                results[job.uid] = True
                return True
            else:
                return False

        # This time test with two interdependent jobs
        dag = DAG()
        dag.add_vertex("1")
        dag.add_vertex("2")
        s = Scheduler(Scheduler.simple_provider(NopJob), tokens=2, collect=collect)
        s.run(dag)
        assert s.max_active_jobs == 2
        assert results["1"]
        assert results["2"]

    def test_skip(self):
        """Simple example in which all the tests are skipped."""
        results = {}

        def get_job(uid, data, predecessors, notify_end):
            result = NopJob(uid, data, notify_end)
            result.should_skip = True
            return result

        def collect(job):
            results[job.uid] = job.timing_info

        # This time test with two interdependent jobs
        dag = DAG()
        dag.add_vertex("1")
        dag.add_vertex("2")
        s = Scheduler(get_job, tokens=2, collect=collect)
        s.run(dag)

        # Check start_time end_time to be sure tests have not been run
        for k, v in list(results.items()):
            assert v.start_time is None
            assert v.stop_time is None

    def test_timeout(self):
        """Ensure that jobs are interrupted correctly on timeout."""
        results = {}
        pytest.importorskip("psutil")

        def get_job(uid, data, predecessors, notify_end):
            return SleepJob(uid, data, notify_end)

        def collect(job):
            results[job.uid] = job

        dag = DAG()
        dag.add_vertex("1")
        dag.add_vertex("2")
        s = Scheduler(get_job, tokens=2, collect=collect, job_timeout=2)
        s.run(dag)

        for k, v in list(results.items()):
            assert v.interrupted

    def test_keyboard_interrupt(self):
        """Ensure that jobs can be interrupted."""
        results = {}
        pytest.importorskip("psutil")

        def get_job(uid, data, predecessors, notify_end):
            return NopJob(uid, data, notify_end)

        def collect(job):
            results[job.uid] = job

        dag = DAG()
        dag.add_vertex("1")
        dag.add_vertex("2")
        s = Scheduler(get_job, tokens=2, collect=collect, job_timeout=2)

        # fake log_state that will raise a KeyboardInterrupt
        def fake_log_state():
            raise KeyboardInterrupt

        s.log_state = fake_log_state

        with pytest.raises(KeyboardInterrupt):
            s.run(dag)

        for k, v in list(results.items()):
            assert v.interrupted

    def test_collect_feedback_scheme(self):
        """Collect feedback construction.

        Scheme in which if a job predecessor "fails" then job is skipped
        In order to do that get_job and collect should have access to
        common data. Note that scheduler ensure that these functions
        are called sequentially.
        """

        class SchedulerContext(object):
            def __init__(self):
                # Save in results tuples with first element being a bool
                # indicating success or failure and the second the job itself
                self.results = {}

            def get_job(self, uid, data, predecessors, notify_end):
                result = NopJob(uid, data, notify_end)

                # If any of the predecessor failed skip the job
                for k in predecessors:
                    if not self.results[k][0]:
                        result.should_skip = True
                return result

            def collect(self, job):
                if job.should_skip:
                    # Skipped jobs are considered failed
                    self.results[job.uid] = [False, job]
                else:
                    # Job '2' is always failing
                    if job.uid == "2":
                        self.results[job.uid] = [False, job]
                    else:
                        self.results[job.uid] = [True, job]

        dag = DAG()
        dag.add_vertex("1")
        dag.add_vertex("2")
        dag.add_vertex("3", predecessors=["1", "2"])
        dag.add_vertex("4", predecessors=["3"])
        c = SchedulerContext()
        s = Scheduler(c.get_job, tokens=2, collect=c.collect)
        s.run(dag)

        assert (
            not c.results["2"][1].should_skip and not c.results["2"][0]
        ), 'job "2" is run and should be marked as failed'
        assert c.results["3"][1].should_skip, 'job "3" should be skipped'
        assert c.results["4"][1].should_skip, 'job "4" should be skipped'
