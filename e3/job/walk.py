from __future__ import absolute_import, division, print_function

import abc
import logging

from e3.anod.status import ReturnValue
from e3.job import EmptyJob
from e3.job.scheduler import DEFAULT_JOB_MAX_DURATION, Scheduler


class Walk(object):
    """An abstract class scheduling and executing a DAG of actions.

    :ivar actions: DAG of actions to perform.
    :vartype actions: DAG
    :ivar job_status: A dictionary of job status (ReturnValue), indexed by
        job unique IDs.
    :vartype: dict
    :ivar scheduler: The scheduler used to schedule an execute all
        the actions.
    :vartype scheduler: e3.job.scheduler.Scheduler
    """

    def __init__(self, actions):
        """Object initializer.

        :param actions: DAG of actions to perform.
        :type actions: DAG
        """
        self.actions = actions
        self.job_status = {}
        self.set_scheduling_params()
        self.scheduler = Scheduler(
            job_provider=self.get_job, collect=self.collect,
            queues=self.queues, tokens=self.tokens,
            job_timeout=self.job_timeout)

        self.scheduler.run(self.actions)

    def set_scheduling_params(self):
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
        self.queues = None
        self.tokens = 1
        self.job_timeout = DEFAULT_JOB_MAX_DURATION

    def create_failed_job(self, uid, data, predecessors, reason, notify_end):
        """Return a failed job.

        This method always returns an EmptyJob. Deriving classes may
        override this method if they need something more specific.

        :param uid: A unique Job ID.
        :type uid: str
        :param data: Data associated to the job to create.
        :type data: T
        :param predecessors: A list of predecessor jobs, or None.
        :type predecessors: list[str] | None
        :param reason: If not None, the reason for creating a failed job.
        :type reason: str | None
        :notify_end: Same as the notify_end parameter in Job.__init__.
        :type notify_end: str -> None
        :rtype: Job
        """
        return EmptyJob(uid, data, notify_end)

    @abc.abstractmethod
    def create_job(self, uid, data, predecessors, notify_end):
        """Create a ProcessJob.

        :param uid: A unique Job ID.
        :type uid: str
        :param data: Data associated to the job to create.
        :type data: T
        :param predecessors: A list of predecessor jobs, or None.
        :type predecessors: list[str] | None
        :notify_end: Same as the notify_end parameter in Job.__init__.
        :type notify_end: str -> None
        :rtype: ProcessJob
        """
        pass  # all: no cover

    @abc.abstractmethod
    def request_requeue(self, job):
        """Requeue the given job.

        Return True if the job has been requeued, False otherwise.

        :param job: The job to requeue.
        :type job: ProcessJob
        :rtype: bool
        """
        pass  # all: no cover

    def get_job(self, uid, data, predecessors, notify_end):
        """Return a Job.

        Same as self.create_job except that this function first checks
        whether any of the predecessors might have failed, in which case
        the failed job (creating using the create_failed_job method)
        is returned.

        :rtype: Job
        """
        # First check status of all predecessors
        failed_predecessors = [k for k in predecessors
                               if self.job_status[k] not in
                               (ReturnValue.success,
                                ReturnValue.skip,
                                ReturnValue.force_skip)]
        if failed_predecessors:
            force_fail = "Event failed because of prerequisite failure:\n"
            force_fail += "\n".join(["  " + str(self.actions[k])
                                     for k in failed_predecessors])
            return self.create_failed_job(uid, data, predecessors,
                                          force_fail, notify_end)

        return self.create_job(uid, data, predecessors, notify_end)

    def collect(self, job):
        """Collect all the results from the given job.

        :param job: The job whose results we need to collect.
        :type job: ProcessJob
        """
        self.job_status[job.uid] = ReturnValue(job.status)

        if job.should_skip:
            if job.status not in (ReturnValue.force_fail,
                                  ReturnValue.force_skip):
                logging.info("[queue=%-10s status=%3d time=%5ds] %s",
                             job.queue_name, self.job_status[job.uid],
                             0, job.data)
            return False

        logging.info("[queue=%-10s status=%3d time=%5ds] %s",
                     job.queue_name,
                     job.status.value,
                     int(job.timing_info.duration),
                     job.data)

        requeued = False
        if self.job_status[job.uid] == ReturnValue.notready:
            requeued = self.request_requeue(job)

        return requeued
