import sys

from e3.anod.status import ReturnValue
from e3.job import EmptyJob, ProcessJob


class TestJob(object):
    def test_run_empty_job(self):
        """Try running an empty job...

        In theory, trying to run an EmptyJob does not make sense,
        since the job's should_skip is True. But, in practice,
        verify that nothing bad happens if someone tries it.

        Also, this allows us to cover this part of the code,
        since the e3.job.scheduler.Scheduler class does not
        do it for us (for the reason specified above).
        """
        job = EmptyJob("1", None, print, ReturnValue.success)
        assert job.should_skip is True
        assert job.status == ReturnValue.success

        job.start(1)
        assert job.should_skip is True
        assert job.status == ReturnValue.success

    def test_process_job_status_before_run(self):
        """Check the status of a ProcessJob before running it.

        Normally, we don't expect anyone to try this, but in case
        it happens, this unit-test makes sure nothing bad happens.
        """

        class EmptyProcessJob(ProcessJob):
            def cmdline(self):
                return [sys.executable, "-c", "pass"]

        job = EmptyProcessJob("1", None, print)
        assert job.status is ReturnValue.notready

    def test_invalid_job_status(self, caplog):
        """Verify that when the return code is invalid we return a failure."""

        class InvalidProcessJob(ProcessJob):
            cmdline = [sys.executable, "-c", "import sys; sys.exit(6)"]

        job = InvalidProcessJob("myuid", {}, None)
        job.run()
        assert job.status is ReturnValue.failure
        assert "job myuid returned an unknown status 6" in caplog.text

    def test_spawn_issue(self):
        """Verify that status is set to failure when the spawn fails."""

        class SpawnIssueProcessJob(ProcessJob):
            @property
            def cmdline(self):
                # This will be called by self.run() and simulate an error
                # when spawning the job
                raise IOError("spawn issue")

        job = SpawnIssueProcessJob("myuid", {}, None)
        job.run()
        assert job.status is ReturnValue.failure
