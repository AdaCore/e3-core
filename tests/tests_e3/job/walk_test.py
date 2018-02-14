from __future__ import absolute_import, division, print_function

import os
import sys

from e3.anod.status import ReturnValue
from e3.collection.dag import DAG
from e3.fingerprint import Fingerprint
from e3.fs import rm
from e3.job import EmptyJob, Job, ProcessJob
from e3.job.walk import Walk

import pytest

# A directory where we have the equivalent of a sandbox; basically,
# a place where we store some information as we perform the actions
# of a given DAG.
SBX_DIR = os.path.join(os.getcwd(), 'sbx')

# A place where to store fingerprints...
FINGERPRINT_DIR = os.path.join(SBX_DIR, 'fingerprints')

# A place where to store anything else that we might need between
# two runs via the Walk class.
SBX_TMP_DIR = os.path.join(SBX_DIR, 'tmp')


@pytest.fixture()
def setup_sbx(request):
    """Automatically create a (temporary) sandbox.

    That sandbox is created before each test gets executed, and
    a finalizer is put in place to automatically delete that
    directory upon test tear-down.
    """
    def delete_sbx():
        if os.path.exists(SBX_DIR):
            rm(SBX_DIR, True)
    request.addfinalizer(delete_sbx)

    delete_sbx()
    os.mkdir(SBX_DIR)
    os.mkdir(FINGERPRINT_DIR)
    os.mkdir(SBX_TMP_DIR)


def source_fullpath(uid):
    """Return the fullpath of a job's sources, if present.

    In our testcase environment, we will consider that, if a DAG's action
    (corresponding to the given Job ID) depends on some sources, those
    sources are in a file called "<uid>.txt" where uid is the action's
    Job ID. Not all actions need sources, so the filename returned
    may or may not exist. Or said differently: if the file exists,
    then the action depends on the "source" filename returned by this
    function; if it does not, then the action does not depend on sources.

    :param uid: A unique Job ID.
    :type uid: str
    :rtype: str
    """
    return os.path.join(SBX_TMP_DIR, uid + '.txt')


class DryRunJob(EmptyJob):
    """A job that does nothing, created when in dry-run mode.

    This class is identical to the EmptyJob class, but having it allows
    us to differentiate between the EmptyJob objects that e3 creates,
    and these jobs we create when in dry-run mode.
    """


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
    dry_run_mode = False

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
        if self.dry_run_mode:
            job = DryRunJob(uid, data, notify_end,
                            status=ReturnValue.force_skip)
        elif uid.endswith('do-nothing'):
            job = DoNothingJob(uid, data, notify_end)
        else:
            job = ControlledJob(uid, data, notify_end)
        return job

    def get_job(self, uid, data, predecessors, notify_end):
        # Normally, deriving classes of class Walk are not expected
        # to override this method. However, we need to do it here
        # as a way to record some information each time this method
        # is called, so as to be able to verify some aspects of
        # the class' behavior.
        job = super(SimpleWalk, self).get_job(uid, data, predecessors,
                                              notify_end)
        self.saved_jobs[job.uid] = job
        return job


class FingerprintWalk(SimpleWalk):
    @classmethod
    def fingerprint_filename(cls, uid):
        return os.path.join(FINGERPRINT_DIR, uid)

    def compute_new_fingerprint(self, uid):
        f = Fingerprint()
        for pred_uid in self.actions.vertex_predecessors[uid]:
            pred_fingerprint = self.load_previous_fingerprint(pred_uid)
            if pred_fingerprint is None:
                # We cannot execute this new action, since one of
                # its predecessors has either not been performed,
                # or was performed but failed. So we cannot compute
                # a fingerprint for this action either.
                return None
            f.add('pred:%s' % pred_uid, pred_fingerprint.sha1())
        if os.path.exists(source_fullpath(uid)):
            f.add_file(source_fullpath(uid))
        return f

    def save_fingerprint(self, uid, fingerprint):
        if self.dry_run_mode:
            # In dry-run mode, we don't do anything, so we should not
            # touch the fingerprint either.
            return

        filename = self.fingerprint_filename(uid)
        if fingerprint is None:
            if os.path.exists(filename):
                os.remove(filename)
        else:
            fingerprint.save_to_file(filename)

    def load_previous_fingerprint(self, uid):
        # In dry-run mode, the fingerprints on file are let untouched,
        # so they might be out of date compared to this job's status
        # as part of this dry run. So, if we have already computed
        # the fingerprint before, use that.
        if self.dry_run_mode and uid in self.new_fingerprints:
            return self.new_fingerprints[uid]

        filename = self.fingerprint_filename(uid)
        if os.path.exists(filename):
            return Fingerprint.load_from_file(filename)
        else:
            return None


class FingerprintWalkDryRun(FingerprintWalk):
    dry_run_mode = True


@pytest.mark.parametrize('walk_class', [SimpleWalk, FingerprintWalk])
class TestWalk(object):
    def test_good_job_no_predecessors(self, walk_class, setup_sbx):
        """Simple case of a leaf job."""
        actions = DAG()
        actions.add_vertex('1')
        c = walk_class(actions)

        job = c.saved_jobs['1']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

        assert c.job_status == {'1': ReturnValue.success}
        assert c.requeued == {}

        # In the situation where we are using fingerprints,
        # verify the behavior when re-doing a walk with
        # the same DAG.

        if walk_class == FingerprintWalk:
            r2 = walk_class(actions)

            job = r2.saved_jobs['1']
            assert isinstance(job, EmptyJob)
            assert job.should_skip is True
            assert job.status == ReturnValue.skip

            assert r2.job_status == {'1': ReturnValue.skip}
            assert r2.requeued == {}

    def test_bad_job_no_predecessors(self, walk_class, setup_sbx):
        """Simple case of a leaf job failing."""
        actions = DAG()
        actions.add_vertex('1.bad')
        c = walk_class(actions)

        job = c.saved_jobs['1.bad']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue(1)
        assert c.job_status == {'1.bad': ReturnValue(1)}
        assert c.requeued == {}

        # In the situation where we are using fingerprints,
        # verify the behavior when re-doing a walk with
        # the same DAG.

        if walk_class == FingerprintWalk:
            r2 = walk_class(actions)

            job = r2.saved_jobs['1.bad']
            assert isinstance(job, ControlledJob)
            assert job.should_skip is False
            assert job.status == ReturnValue(1)
            assert r2.job_status == {'1.bad': ReturnValue(1)}
            assert r2.requeued == {}

    def test_failed_predecessor(self, walk_class, setup_sbx):
        """Simulate the scenarior when a predecessor failed."""
        actions = DAG()
        actions.add_vertex('1.bad')
        actions.add_vertex('2', predecessors=['1.bad'])
        c = walk_class(actions)

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

        # In the situation where we are using fingerprints,
        # verify the behavior when re-doing a walk with
        # the same DAG.

        if walk_class == FingerprintWalk:
            r2 = walk_class(actions)

            job = r2.saved_jobs['1.bad']
            assert isinstance(job, ControlledJob)
            assert job.should_skip is False
            assert job.status == ReturnValue(1)

            job = r2.saved_jobs['2']
            assert isinstance(job, EmptyJob)
            assert job.should_skip is True
            assert job.status == ReturnValue.failure

            assert r2.job_status == {'1.bad': ReturnValue(1),
                                     '2': ReturnValue.failure}
            assert r2.requeued == {}

    def test_job_not_ready_then_ok(self, walk_class, setup_sbx):
        """Rerunning a job that first returned notready."""
        actions = DAG()
        actions.add_vertex('1.notready:once')
        c = walk_class(actions)

        job = c.saved_jobs['1.notready:once']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

        assert c.job_status == {'1.notready:once': ReturnValue.success}
        assert c.requeued == {'1.notready:once': 1}

        # In the situation where we are using fingerprints,
        # verify the behavior when re-doing a walk with
        # the same DAG.

        if walk_class == FingerprintWalk:
            r2 = walk_class(actions)

            job = r2.saved_jobs['1.notready:once']
            assert isinstance(job, EmptyJob)
            assert job.should_skip is True
            assert job.status == ReturnValue.skip

            assert r2.job_status == {'1.notready:once': ReturnValue.skip}
            assert r2.requeued == {}

    def test_job_never_ready(self, walk_class, setup_sbx):
        """Trying to run a job repeatedly returning notready."""
        actions = DAG()
        actions.add_vertex('1.notready:always')
        c = walk_class(actions)

        job = c.saved_jobs['1.notready:always']
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.notready

        assert c.job_status == {'1.notready:always': ReturnValue.notready}
        assert c.requeued == {'1.notready:always': 3}

        # In the situation where we are using fingerprints,
        # verify the behavior when re-doing a walk with
        # the same DAG.

        if walk_class == FingerprintWalk:
            r2 = walk_class(actions)

            job = r2.saved_jobs['1.notready:always']
            assert isinstance(job, ControlledJob)
            assert job.should_skip is False
            assert job.status == ReturnValue.notready

            assert r2.job_status == {'1.notready:always': ReturnValue.notready}
            assert r2.requeued == {'1.notready:always': 3}

    def test_do_nothing_job(self, walk_class, setup_sbx):
        """Test DAG leading us to create a DoNothingJob object."""
        actions = DAG()
        actions.add_vertex('1.do-nothing')
        actions.add_vertex('2', predecessors=['1.do-nothing'])
        c = walk_class(actions)

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

        # In the situation where we are using fingerprints,
        # verify the behavior when re-doing a walk with
        # the same DAG.

        if walk_class == FingerprintWalk:
            r2 = walk_class(actions)

            job = r2.saved_jobs['1.do-nothing']
            assert isinstance(job, EmptyJob)
            assert job.should_skip is True
            assert job.status == ReturnValue.skip

            job = r2.saved_jobs['2']
            assert isinstance(job, EmptyJob)
            assert job.should_skip is True
            assert job.status == ReturnValue.skip

            assert r2.job_status == {'1.do-nothing': ReturnValue.skip,
                                     '2': ReturnValue.skip}
            assert r2.requeued == {}


def test_source_deps(setup_sbx):
    """Try runs with source dependencies changing between runs."""
    actions = DAG()
    actions.add_vertex('1')
    actions.add_vertex('2', predecessors=['1'])
    actions.add_vertex('3')
    actions.add_vertex('4', predecessors=['2', '3'])
    actions.add_vertex('5')

    # Create source dependencies for each actions
    for uid in ('1', '2', '3', '4', '5'):
        with open(source_fullpath(uid), 'w') as f:
            f.write('contents of sources for action %s\n' % uid)

    # Now, execute our planned actions

    r1 = FingerprintWalk(actions)

    for uid in ('1', '2', '3', '4', '5'):
        job = r1.saved_jobs[uid]
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

    assert r1.job_status == {'1': ReturnValue.success,
                             '2': ReturnValue.success,
                             '3': ReturnValue.success,
                             '4': ReturnValue.success,
                             '5': ReturnValue.success}
    assert r1.requeued == {}

    # Executing it again should result in all actions being skipped.

    r2 = FingerprintWalk(actions)

    for uid in ('1', '2', '3', '4', '5'):
        job = r2.saved_jobs[uid]
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.skip

    assert r2.job_status == {'1': ReturnValue.skip,
                             '2': ReturnValue.skip,
                             '3': ReturnValue.skip,
                             '4': ReturnValue.skip,
                             '5': ReturnValue.skip}
    assert r2.requeued == {}

    # Now change the sources of action '5', and run the actions
    # again. Only '5' should be executed.

    with open(source_fullpath('5'), 'a') as f:
        f.write("Some more sources\n")

    r3 = FingerprintWalk(actions)

    for uid in ('1', '2', '3', '4'):
        job = r3.saved_jobs[uid]
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.skip

    for uid in ('5', ):
        job = r3.saved_jobs[uid]
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

    assert r3.job_status == {'1': ReturnValue.skip,
                             '2': ReturnValue.skip,
                             '3': ReturnValue.skip,
                             '4': ReturnValue.skip,
                             '5': ReturnValue.success}
    assert r3.requeued == {}

    # Executing it again should result in all actions being skipped.

    r4 = FingerprintWalk(actions)

    for uid in ('1', '2', '3', '4', '5'):
        job = r4.saved_jobs[uid]
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.skip

    assert r4.job_status == {'1': ReturnValue.skip,
                             '2': ReturnValue.skip,
                             '3': ReturnValue.skip,
                             '4': ReturnValue.skip,
                             '5': ReturnValue.skip}
    assert r4.requeued == {}

    # Change the sources of '1' and '2'. We expect '1' and '2' to
    # be re-run, as well as their dependences ('4', in this case).

    for uid in ('1', '2'):
        with open(source_fullpath(uid), 'a') as f:
            f.write("Additional information\n")

    r5 = FingerprintWalk(actions)

    for uid in ('3', '5'):
        job = r5.saved_jobs[uid]
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.skip

    for uid in ('1', '2', '4'):
        job = r5.saved_jobs[uid]
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

    assert r5.job_status == {'1': ReturnValue.success,
                             '2': ReturnValue.success,
                             '3': ReturnValue.skip,
                             '4': ReturnValue.success,
                             '5': ReturnValue.skip}
    assert r5.requeued == {}

    # Change the sources of '1'. We expect '1' be re-run, and
    # as a consequence of that, '2' and '4' also should be rerun.

    with open(source_fullpath('1'), 'a') as f:
        f.write("# Small comment\n")

    r5 = FingerprintWalk(actions)

    for uid in ('3', '5'):
        job = r5.saved_jobs[uid]
        assert isinstance(job, EmptyJob)
        assert job.should_skip is True
        assert job.status == ReturnValue.skip

    for uid in ('1', '2', '4'):
        job = r5.saved_jobs[uid]
        assert isinstance(job, ControlledJob)
        assert job.should_skip is False
        assert job.status == ReturnValue.success

    assert r5.job_status == {'1': ReturnValue.success,
                             '2': ReturnValue.success,
                             '3': ReturnValue.skip,
                             '4': ReturnValue.success,
                             '5': ReturnValue.skip}
    assert r5.requeued == {}


def test_dry_run(setup_sbx):
    """Simulate the use actions with "dry run" behavior."""
    actions = DAG()
    actions.add_vertex('1')
    actions.add_vertex('2', predecessors=['1'])

    # First run in dry-run mode. Both actions are turned into
    # empty jobs with a force_skip status.

    r1 = FingerprintWalkDryRun(actions)

    job = r1.saved_jobs['1']
    assert isinstance(job, DryRunJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.force_skip

    job = r1.saved_jobs['2']
    assert isinstance(job, DryRunJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.force_skip

    assert r1.job_status == {'1': ReturnValue.force_skip,
                             '2': ReturnValue.force_skip}
    assert r1.requeued == {}

    # Try it again in dry-mode; we should get the same result.

    r2 = FingerprintWalkDryRun(actions)

    job = r2.saved_jobs['1']
    assert isinstance(job, DryRunJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.force_skip

    job = r2.saved_jobs['2']
    assert isinstance(job, DryRunJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.force_skip

    assert r2.job_status == {'1': ReturnValue.force_skip,
                             '2': ReturnValue.force_skip}
    assert r2.requeued == {}

    # Now, get action '1' done in normal (non-dry-run) mode.

    one_only = DAG()
    one_only.add_vertex('1')

    r3 = FingerprintWalk(one_only)

    job = r3.saved_jobs['1']
    assert isinstance(job, ControlledJob)
    assert job.should_skip is False
    assert job.status == ReturnValue.success

    assert r3.job_status == {'1': ReturnValue.success}
    assert r3.requeued == {}

    # Try again the original plam in dry-run mode.
    #
    # This time, since '1' has been actually completed in a previous
    # run, action '1' should be skipped, and action '2' should be
    # a dry-run job...

    r4 = FingerprintWalkDryRun(actions)

    job = r4.saved_jobs['1']
    assert isinstance(job, EmptyJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.skip

    job = r4.saved_jobs['2']
    assert isinstance(job, DryRunJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.force_skip

    assert r4.job_status == {'1': ReturnValue.skip,
                             '2': ReturnValue.force_skip}
    assert r4.requeued == {}

    # Run it again, this time in normal (non-dry-run) mode.
    #
    # This time, action '2' gets scheduled for real...

    r5 = FingerprintWalk(actions)

    job = r5.saved_jobs['1']
    assert isinstance(job, EmptyJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.skip

    job = r5.saved_jobs['2']
    assert isinstance(job, ControlledJob)
    assert job.should_skip is False
    assert job.status == ReturnValue.success

    assert r5.job_status == {'1': ReturnValue.skip,
                             '2': ReturnValue.success}
    assert r5.requeued == {}

    # One more time, in dry-run mode again.
    #
    # There is nothing to be done, so the results should be
    # both actions are skipped.

    r6 = FingerprintWalkDryRun(actions)

    job = r6.saved_jobs['1']
    assert isinstance(job, EmptyJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.skip

    job = r6.saved_jobs['2']
    assert isinstance(job, EmptyJob)
    assert job.should_skip is True
    assert job.status == ReturnValue.skip

    assert r6.job_status == {'1': ReturnValue.skip,
                             '2': ReturnValue.skip}
    assert r6.requeued == {}
