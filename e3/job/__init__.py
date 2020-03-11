from collections import namedtuple
from datetime import datetime
from e3.anod.status import ReturnValue
from e3.os.process import Run
import abc
import e3.log
import threading

logger = e3.log.getLogger("job")


JobTimingInfo = namedtuple("JobTimingInfo", ["start_time", "stop_time", "duration"])


class Job(object, metaclass=abc.ABCMeta):
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

    lock = threading.RLock()
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
        self.queue_name = "default"
        self.tokens = 1
        with self.lock:
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
        with self.lock:
            self.__start_time = datetime.now()

    def record_stop_time(self):
        """Log the stopping time of a job."""
        with self.lock:
            self.__stop_time = datetime.now()

    @property
    def timing_info(self):
        """Retrieve some job's timing information.

        :return: a JobTimingInfo object
        :rtype: JobTimingInfo
        """
        with self.lock:
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
                with self.lock:
                    interrupted = self.interrupted
                if interrupted:  # defensive code
                    logger.debug("job %s has been cancelled", self.uid)
                else:
                    self.run()
            finally:
                self.record_stop_time()
                self.notify_end(self.uid)

        self.slot = slot
        self.handle = threading.Thread(target=task_function, name=self.uid)
        self.handle.start()

    @abc.abstractmethod
    def run(self):
        """Job activity."""
        pass  # all: no cover

    @property
    def status(self):
        """Return he job's status.

        This is made a property because users of this class should not
        be allowed to set or change it value. The job's status is ...
        a property of the job!

        :return: e3.anod.status.ReturnValue
        """
        return ReturnValue.success

    def interrupt(self):
        """Interrupt current job.

        :rtype: bool
        :return: True if interrupted, False if already interrupted
        """
        with self.lock:
            previous_state = self.interrupted
            self.interrupted = True
        return not previous_state

    def on_start(self, scheduler):
        """Call whenever a job is started.

        This allow the user to do some logging on job startup
        """
        pass

    def on_finish(self, scheduler):
        """Call whenever a job is finished.

        This allow the user to do some logging on job termination
        """
        pass


class EmptyJob(Job):
    """A job which does nothing."""

    def __init__(self, uid, data, notify_end, status=ReturnValue.force_skip):
        """Initialize the EmptyJob.

        :param status: The job's status.
        :type status: e3.anod.status.ReturnValue
        """
        super(EmptyJob, self).__init__(uid, data, notify_end)
        self.should_skip = True
        self.__status = status

    def run(self):
        pass

    @property
    def status(self):
        """See Job.status' description."""
        return self.__status


class ProcessJob(Job, metaclass=abc.ABCMeta):
    """Specialized version of Job that spawn processes.

    :ivar proc_handle: None when an object of this class is initialized.
        An e3.os.process.Run object after the "run" method is called.
    :vartype proc_handle: e3.os.process.Run | None
    """

    def __init__(self, uid, data, notify_end):
        super(ProcessJob, self).__init__(uid, data, notify_end)
        self.proc_handle = None

        # Detect spawn issue to avoid returning "notready"
        # and creating a loop
        self.__spawn_error = False

    def run(self):
        """Run the job."""
        cmd_options = self.cmd_options

        # Do non blocking spawn followed by a wait in order to have
        # self.proc_handle set. This allows support for interrupt.
        cmd_options["bg"] = True
        with self.lock:
            if self.interrupted:  # defensive code
                logger.debug("job %s has been cancelled", self.uid)
                return
            try:
                cmdline = self.cmdline
                assert cmdline is not None, "cmdline cannot be None"

                proc_handle = Run(cmdline, **cmd_options)
                self.proc_handle = proc_handle
            except Exception:
                logger.exception("error when spawing job %s", self.uid)
                self.__spawn_error = True
                return
        proc_handle.wait()
        logger.debug(
            "job %s status %s (pid:%s)", self.uid, proc_handle.status, proc_handle.pid
        )

    @property
    def status(self):
        """See Job.status' description."""
        if self.__spawn_error:
            return ReturnValue.failure
        elif self.proc_handle is None:
            return ReturnValue.notready
        else:
            try:
                return ReturnValue(self.proc_handle.status)
            except ValueError:
                logger.exception(
                    "job %s returned an unknown status %s",
                    self.uid,
                    self.proc_handle.status,
                )
                return ReturnValue.failure

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
        return {"output": None}

    def interrupt(self):
        """Kill running process tree."""
        if super(ProcessJob, self).interrupt():
            if self.proc_handle is None:  # defensive code
                logger.debug("cancel job %s", self.uid)
            elif self.proc_handle.is_running():
                logger.debug("kill job %s", self.uid)
                self.proc_handle.kill(recursive=True)
            else:  # defensive code
                logger.debug("cannot interrupt, job %s has finished", self.uid)
