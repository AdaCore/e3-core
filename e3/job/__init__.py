from __future__ import absolute_import
from __future__ import print_function

from datetime import datetime
from e3.os.process import Run
import abc
import e3.log
import threading

logger = e3.log.getLogger('job')


class Job(object):
    """Class to handle a single Job.

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
        self.thread = None
        self.start_time = None
        self.stop_time = None
        self.should_skip = False
        self.interrupted = False
        self.queue_name = 'default'
        self.tokens = 1

    def start(self, slot):
        """Launch the job.

        :param slot: slot number
        :type slot: int
        """
        def task_function():
            try:
                self.run()
            finally:
                self.stop_time = datetime.now()
                self.notify_end(self.uid)

        self.handle = threading.Thread(target=task_function,
                                       name=self.uid)
        self.start_time = datetime.now()
        self.handle.start()
        self.slot = slot

    @abc.abstractmethod
    def run(self):
        """Job activity."""
        pass

    def interrupt(self):
        """Interrupt current job."""
        self.interrupted = True


class ProcessJob(Job):
    """Specialized version of Job that spawn processes."""

    __metaclass__ = abc.ABCMeta

    def run(self):
        """Internal function."""
        cmd_options = self.cmd_options

        # Do non blocking spawn followed by a wait in order to have
        # self.proc_handle set. This allows support for interrupt.
        cmd_options['bg'] = True
        self.proc_handle = Run(self.cmdline, **cmd_options)
        self.proc_handle.wait()

    @abc.abstractproperty
    def cmdline(self):
        """Command line of the process to be spawned.

        :return: the command line
        :rtype: list[str]
        """
        pass

    @property
    def cmd_options(self):
        """Process options.

        :return: options for e3.os.process.Run as a dict
        :rtype: dict
        """
        return {}

    def interrupt(self):
        """Kill running process tree."""
        if hasattr(self, 'proc_handle') and \
                self.proc_handle and \
                self.proc_handle.is_running():
            logger.debug('interrrupt job %s', self.uid)
            self.proc_handle.kill(recursive=True)
            self.interrupted = True
