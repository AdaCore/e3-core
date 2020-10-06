from __future__ import annotations

import abc
import logging
from itertools import chain
from typing import TYPE_CHECKING

from e3.anod.status import ReturnValue
from e3.job import EmptyJob
from e3.job.scheduler import DEFAULT_JOB_MAX_DURATION, Scheduler

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, FrozenSet, Optional, Set
    from e3.collection.dag import DAG
    from e3.fingerprint import Fingerprint
    from e3.job import Job, ProcessJob


class Walk:
    """An abstract class scheduling and executing a DAG of actions.

    :ivar actions: DAG of actions to perform.
    :vartype actions: DAG
    :ivar prev_fingerprints: A dict of e3.fingerprint.Fingerprint objects,
          indexed by the corresponding job ID. This dictionary contains
          the former fingerprints a given job or None if there was no
          such fingerprint.
          (with the job corresponding to a given entry in the DAG of
          actions).
    :vartype prev_fingerprints: Dict[str, Optional[Fingerprint]]
    :ivar new_fingerprints: A dict of e3.fingerprint.Fingerprint objects,
        indexed by the corresponding job ID. This dictionary contains
        the fingerprints we compute each time we create a new job
        (with the job corresponding to a given entry in the DAG of
        actions).
    :vartype new_fingerprints: Dict[str, Optional[Fingerprint]]
    :ivar job_status: A dictionary of job status (ReturnValue), indexed by
        job unique IDs.
    :vartype job_status: Dict[str, ReturnValue]
    :ivar scheduler: The scheduler used to schedule and execute all
        the actions.
    :vartype scheduler: e3.job.scheduler.Scheduler
    """

    def __init__(self, actions: DAG):
        """Object initializer.

        :param actions: DAG of actions to perform.
        """
        self.actions = actions
        self.prev_fingerprints: Dict[str, Optional[Fingerprint]] = {}
        self.new_fingerprints: Dict[str, Optional[Fingerprint]] = {}
        self.job_status: Dict[str, ReturnValue] = {}
        self.queues: Dict[str, int] = {}
        self.tokens = 1
        self.job_timeout = DEFAULT_JOB_MAX_DURATION
        self.set_scheduling_params()
        self.failure_source: Dict[str, Set[str]] = {}

        self.scheduler = Scheduler(
            job_provider=self.get_job,
            collect=self.collect,  # type: ignore
            queues=self.queues,
            tokens=self.tokens,
            job_timeout=self.job_timeout,
        )

        self.scheduler.run(self.actions)

    def set_scheduling_params(self) -> None:
        """Set the parameters used when creating the scheduler.

        This method is expected to set the following attributes:
            - self.queues: Same as parameter of the same name
                in e3.job.scheduler.Scheduler.__init__.
            - self.tokens: Likewise.
            - self.job_timeout: Likewise.

        This method provides a default setup where the scheduler has
        1 token and 1 queue, and where the job's maximum duration is
        DEFAULT_JOB_MAX_DURATION. Child classes requiring different
        scheduling parameters should override this method.
        """
        pass

    def compute_fingerprint(
        self, uid: str, data: Any, is_prediction: bool = False
    ) -> Optional[Fingerprint]:
        """Compute the given action's Fingerprint.

        This method is expected to return a Fingerprint corresponding
        to the state of the system should the given action be executed
        and succesful. It can also return None if keeping track of
        the result of past actions is not necessary.

        This implementation always returns None. Child classes requiring
        a different behavior may override this method.

        :param uid: A unique Job ID.
        :param data: Data associated to the job.
        :param is_prediction: If True this is an attempt to compute the
            fingerprint before launching the job. In that case if the
            function returns None then the job will always be launched.
            When False, this is the computation done after running the
            job (that will be the final fingerprint saved for future
            comparison)
        """
        return None

    def save_fingerprint(self, uid: str, fingerprint: Optional[Fingerprint]) -> None:
        """Save the given fingerprint.

        For systems that require fingerprint persistence, this method
        is expected to save the fingerprint somewhere -- typically
        inside a file. Passing None as the fingerprint causes
        the fingerprint to be deleted instead.

        This implementation does nothing. Child classes taking advantage
        of fingerprint support should override this method to save
        the fingerprint at the location of their choice and using
        the format that suits them.

        :param uid: A unique Job ID.
        :param fingerprint: The fingerprint corresponding to the given
            job, or None, if the fingerprint should be deleted instead
            of saved.
        """
        pass

    def load_previous_fingerprint(self, uid: str) -> Optional[Fingerprint]:
        """Get the fingerprint from the given action's previous execution.

        This method is expected to have the following behavior:
            - If the given action has already previously been executed
              and its fingerprint saved (see method "save_fingerprint"
              above), then load and return it;
            - Otherwise, return None.

        This implementation always returns None, providing a behavior
        where re-executing a given action always results in the
        corresponding job being executed. Child classes requiring
        a different behavior may override this method.

        :param uid: A unique Job ID.
        """
        return None

    def should_execute_action(
        self,
        uid: str,
        previous_fingerprint: Optional[Fingerprint],
        new_fingerprint: Optional[Fingerprint],
    ) -> bool:
        """Return True if the given action should be performed.

        The purpose of this function is to provide a way to determine,
        based on the previous fingerprint, and the new one, whether
        the user of this class wants us to launch the action or not.

        The default implementation implements the following strategy:
            - when fingerprints are not in use, always execution
              the given action;
            - when fingerprints are in use, execute the given action
              if the fingerprint has changed.

        However, child classes may want to override this method
        to implement alternative strategies.

        :param uid: A unique Job ID.
        :param previous_fingerprint: The fingerprint from the previous
            from the action's previous run.  None if the action has not
            been previously executed.
        :param new_fingerprint: The fingerprint from the previous
            from the action's previous run.  None if the action has not
            been previously executed.
        """
        if previous_fingerprint is None or new_fingerprint is None:
            return True
        for pred_uid in self.actions.get_predecessors(uid):
            if self.new_fingerprints[str(pred_uid)] is None:
                # One of the predecessors has no fingerprint, so
                # this node's new_fingerprint cannot tell us whether
                # this dependency has changed or not. We therefore
                # need to run this action.
                return True
        return previous_fingerprint != new_fingerprint

    def create_skipped_job(
        self,
        uid: str,
        data: Any,
        predecessors: FrozenSet[str],
        reason: Optional[str],
        notify_end: Callable[[str], None],
        status: ReturnValue = ReturnValue.failure,
    ) -> Job:
        """Return a failed job.

        This method always returns an EmptyJob. Deriving classes may
        override this method if they need something more specific.

        :param uid: A unique Job ID.
        :param data: Data associated to the job to create.
        :param predecessors: A list of predecessor jobs, or None.
        :param reason: If not None, the reason for creating a failed job.
        :notify_end: Same as the notify_end parameter in Job.__init__.
        """
        return EmptyJob(uid, data, notify_end, status=status)

    @abc.abstractmethod
    def create_job(
        self,
        uid: str,
        data: Any,
        predecessors: FrozenSet[str],
        notify_end: Callable[[str], None],
    ) -> ProcessJob:
        """Create a ProcessJob.

        :param uid: A unique Job ID.
        :param data: Data associated to the job to create.
        :param predecessors: A list of predecessor jobs, or None.
        :notify_end: Same as the notify_end parameter in Job.__init__.
        """
        pass  # all: no cover

    @abc.abstractmethod
    def request_requeue(self, job: ProcessJob) -> bool:
        """Requeue the given job.

        Return True if the job has been requeued, False otherwise.

        :param job: The job to requeue.
        """
        pass  # all: no cover

    def get_job(
        self,
        uid: str,
        data: Any,
        predecessors: FrozenSet[str],
        notify_end: Callable[[str], None],
    ) -> Job:
        """Return a Job.

        Same as self.create_job except that this function first checks
        whether any of the predecessors might have failed, in which case
        the failed job (creating using the create_skipped_job method)
        is returned.
        """
        # Get the latest fingerprint
        self.prev_fingerprints[uid] = self.load_previous_fingerprint(uid)

        # And reset the fingerprint on disk
        self.save_fingerprint(uid, None)

        self.new_fingerprints[uid] = self.compute_fingerprint(
            uid, data, is_prediction=True
        )

        # Check our predecessors. If any of them failed, then return
        # a failed job.
        failed_predecessors = [
            k
            for k in predecessors
            if self.job_status[k]
            not in (
                ReturnValue.success,
                ReturnValue.skip,
                ReturnValue.force_skip,
                ReturnValue.unchanged,
            )
        ]
        if failed_predecessors:
            force_fail = "Event failed because of prerequisite failure:\n"
            force_fail += "\n".join(
                ["  " + str(self.actions[k]) for k in failed_predecessors]
            )

            # Compute the set of job that originate that failure
            self.failure_source[uid] = set(
                chain.from_iterable(
                    [self.failure_source.get(k, [k]) for k in failed_predecessors]
                )
            )
            force_fail += "\n\nOrigin(s) of failure:\n"
            force_fail += "\n".join(
                ["  " + str(self.actions[k]) for k in self.failure_source[uid]]
            )

            return self.create_skipped_job(
                uid,
                data,
                predecessors,
                force_fail,
                notify_end,
                status=ReturnValue.force_fail,
            )

        if self.should_execute_action(
            uid, self.prev_fingerprints[uid], self.new_fingerprints[uid]
        ):
            return self.create_job(uid, data, predecessors, notify_end)
        else:
            return self.create_skipped_job(
                uid, data, predecessors, "skipped", notify_end, status=ReturnValue.skip
            )

    def collect(self, job: ProcessJob) -> bool:
        """Collect all the results from the given job.

        :param job: The job whose results we need to collect.

        :return: True if the job is requeued, False otherwise
        """
        # Only save the fingerprint if the job went as expected (either
        # success or skipped). Since we already removed the previous
        # fingerprint when we created the job, not saving the fingerprint
        # ensures that we try that action again next time (as opposed
        # to skipping it).
        if job.status in (
            ReturnValue.success,
            ReturnValue.force_skip,
            ReturnValue.skip,
            ReturnValue.unchanged,
        ):
            self.new_fingerprints[job.uid] = self.compute_fingerprint(job.uid, job.data)
            self.save_fingerprint(job.uid, self.new_fingerprints[job.uid])

        self.job_status[job.uid] = ReturnValue(job.status)

        if job.should_skip:
            if job.status not in (ReturnValue.force_fail, ReturnValue.force_skip):
                logging.info(
                    "[%-10s %-9s %4ds] %s",
                    job.queue_name,
                    self.job_status[job.uid].name,
                    0,
                    job.data,
                )
            return False

        logging.info(
            "[%-10s %-9s %4ds] %s",
            job.queue_name,
            job.status.name,
            int(job.timing_info.duration),
            job.data,
        )

        requeued = False
        if self.job_status[job.uid] == ReturnValue.notready:
            requeued = self.request_requeue(job)

        return requeued
