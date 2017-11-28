from __future__ import absolute_import, division, print_function

from collections import namedtuple
from datetime import datetime
from e3.anod.status import ReturnValue
from e3.os.process import Run
import abc
import e3.log
import logging
import threading

logger = e3.log.getLogger('job')


JobTimingInfo = namedtuple('JobTimingInfo',
                           ['start_time', 'stop_time', 'duration'])


class Job(object):
    """Handle a single Job.

    :ivar slot: number associated with the job during its execution. At a
        given time only one job have a given slot number.
    :vartype slot: int
    :ivar start_time: time at which job execution started or None if never
        started
    :vartype start_time: datetime.datetime
    :ivar stop_time: time at which job execution ended or None if either
        the job was never run or if the job is still running
    :vartype stop_time: datetime.datetime
    :ivar should_skip: indicator for the scheduler that the job should not
        be executed
    :vartype: bool
    :ivar interrupted: if True it means that job has been interrupted. Can
        be consequence of timeout or Ctrl-C pressed
    :vartype: bool
    :ivar queue_name: name of the queue in which the job has been placed
    :vartype: str
    :ivar tokens: number of tokens (i.e: resources) consumed during the job
        execution
    :vartype: int
    :ivar index: global index indicating the order in which jobs have been
        created. The index is used to implement the default ordering function
        needed to sort Jobs. In the context of ``e3.job.scheduler.Scheduler``
        this means that by default jobs that are created first will have a
        higher priority.
    :vartype: int
    """

    __metaclass__ = abc.ABCMeta
    _lock = threading.Lock()
    index_counter = 0

    def __init__(self, uid, data, notify_end):
        """Initialize worker.

        :param uid: unique work identifier
        :type uid: str
        :param data: work data
        :type data: T
        :param notify_end: function that takes the job uid as parameter. The
            function is called whenever the job finish. The function is
            provided by the scheduler.
        :type notify_end: str -> None
        """
        self.uid = uid
        self.data = data
        self.notify_end = notify_end
        self.slot = None
        self.handle = None
        self.thread = None
        self.__start_time = None
        self.__stop_time = None
        self.should_skip = False
        self.interrupted = False
        self.queue_name = 'default'
        self.tokens = 1
        with self._lock:
            self.index = Job.index_counter
            Job.index_counter += 1

    @property
    def priority(self):
        """Return job priority.

        This is used in ``e3.job.scheduler.Scheduler``.

        :return: int
        """
        return 0

    def record_start_time(self):
        """Log the starting time of a job."""
        with self._lock:
            self.__start_time = datetime.now()

    def record_stop_time(self):
        """Log the stopping time of a job."""
        with self._lock:
            self.__stop_time = datetime.now()

    @property
    def timing_info(self):
        """Retrieve some job's timing information.

        :return: a JobTimingInfo object
        :rtype: JobTimingInfo
        """
        with self._lock:
            start = self.__start_time
            stop = self.__stop_time
        if start is None:
            duration = 0
        else:
            duration = ((stop or datetime.now()) - start).total_seconds()
        return JobTimingInfo(start, stop, duration)

    def start(self, slot):
        """Launch the job.

        :param slot: slot number
        :type slot: int
        """
        def task_function():
            self.record_start_time()
            try:
                with self._lock:
                    interrupted = self.interrupted
                if interrupted:  # defensive code
                    logger.debug('job %s has been cancelled', self.uid)
                else:
                    self.run()
            finally:
                self.record_stop_time()
                self.notify_end(self.uid)

        self.handle = threading.Thread(target=task_function,
                                       name=self.uid)
        self.handle.start()
        self.slot = slot

    @abc.abstractmethod
    def run(self):
        """Job activity."""
        pass  # all: no cover

    def interrupt(self):
        """Interrupt current job.

        :rtype: bool
        :return: True if interrupted, False if already interrupted
        """
        with self._lock:
            previous_state = self.interrupted
            self.interrupted = True
        return not previous_state


class EmptyJob(Job):
    """A job which does nothing.

    :ivar status: The job's status.
    :vartype status: ReturnValue
    """

    def __init__(self, uid, data, notify_end, status=ReturnValue.force_skip):
        """Initialize the EmptyJob.

        :param status: The job's status.
        :type status: ReturnValue
        """
        super(EmptyJob, self).__init__(uid, data, notify_end)
        self.should_skip = True
        self.status = status

    def run(self):
        pass


class ProcessJob(Job):
    """Specialized version of Job that spawn processes.

    :ivar proc_handle: None when an object of this class is initialized.
        An e3.os.process.Run object after the "run" method is called.
    :vartype proc_handle: e3.os.process.Run | None
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, uid, data, notify_end):
        super(ProcessJob, self).__init__(uid, data, notify_end)
        self.proc_handle = None

    def run(self):
        """Run the job."""
        cmd_options = self.cmd_options

        # Do non blocking spawn followed by a wait in order to have
        # self.proc_handle set. This allows support for interrupt.
        cmd_options['bg'] = True
        with self._lock:
            if self.interrupted:  # defensive code
                logger.debug('job %s has been cancelled', self.uid)
                return
            proc_handle = Run(self.cmdline, **cmd_options)
            self.proc_handle = proc_handle
        proc_handle.wait()
        logger.debug('job %s status %s (pid:%s)',
                     self.uid, proc_handle.status, proc_handle.pid)

    @abc.abstractproperty
    def cmdline(self):
        """Return the command line of the process to be spawned.

        :return: the command line
        :rtype: list[str]
        """
        pass  # all: no cover

    @property
    def cmd_options(self):
        """Process options.

        Important note: don't use PIPE for output or error parameters this can
        cause locking error in case the process is interrupted. The default
        redirect output and error to the console.

        The pipe behavior can easily be emulated by writing to a file and
        modifying the run method to read the file content when the process
        finish.

        :return: options for e3.os.process.Run as a dict
        :rtype: dict
        """
        return {'output': None}

    def interrupt(self):
        """Kill running process tree."""
        if super(ProcessJob, self).interrupt():
            if self.proc_handle is None:  # defensive code
                logger.debug('cancel job %s', self.uid)
            elif self.proc_handle.is_running():
                logger.debug('kill job %s', self.uid)
                self.proc_handle.kill(recursive=True)
            else:  # defensive code
                logger.debug('cannot interrupt, job %s has finished', self.uid)


class JobController(object):
    """An abstract class to control a job and its dependencies."""

    @abc.abstractmethod
    def get_job(self, uid, data, predecessors, notify_end):
        """Return a Job.

        :param uid: A unique Job ID.
        :type uid: str
        :param data: Data associated to the job to create.
        :type data: T
        :param predecessors: A list of predecessor jobs, or None.
        :type predecessors: list[str] | None
        :notify_end: Same as the notify_end parameter in Job.__init__.
        :type notify_end: str -> None
        :rtype: Job
        """
        pass  # all: no cover

    @abc.abstractmethod
    def collect(self, job):
        """Collect the status of the given job.

        Return True if the job has been requeued, False otherwise.

        :param job: The job to collect.
        :type job: ProcessJob
        :rtype: bool
        """
        pass  # all: no cover


class StatusBasedJobController(JobController):
    """A job controller taking job status into account.

    :ivar actions: DAG of actions to perform.
    :vartype actions: DAG
    :ivar job_status: A dictionary of job status (ReturnValue), indexed by
        job unique IDs.
    :vartype: dict
    """

    def __init__(self, actions):
        """Initialize a JobController.

        :param actions: DAG of actions to perform.
        :type actions: DAG
        """
        self.actions = actions
        self.job_status = {}

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
        if job.should_skip:
            self.job_status[job.uid] = ReturnValue(job.status)
            if job.status not in (ReturnValue.force_fail,
                                  ReturnValue.force_skip):
                logging.info("[queue=%-10s status=%3d time=%5ds] %s",
                             job.queue_name, self.job_status[job.uid],
                             0, job.data)
            return False

        self.job_status[job.uid] = ReturnValue(job.proc_handle.status)
        logging.info("[queue=%-10s status=%3d time=%5ds] %s",
                     job.queue_name,
                     job.proc_handle.status,
                     int(job.timing_info.duration),
                     job.data)

        requeued = False
        if self.job_status[job.uid] == ReturnValue.notready:
            requeued = self.request_requeue(job)

        return requeued
