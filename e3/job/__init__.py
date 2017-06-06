from __future__ import absolute_import
from __future__ import print_function

from collections import namedtuple
from datetime import datetime
from e3.os.process import Run
import abc
import e3.log
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
    """

    __metaclass__ = abc.ABCMeta
    _lock = threading.Lock()

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

    def record_start_time(self):
        with self._lock:
            self.__start_time = datetime.now()

    def record_stop_time(self):
        with self._lock:
            self.__stop_time = datetime.now()

    @property
    def timing_info(self):
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


class ProcessJob(Job):
    """Specialized version of Job that spawn processes."""

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
