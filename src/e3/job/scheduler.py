import heapq
import time
from datetime import datetime
from queue import Empty, Queue

import e3.log
from e3.collection.dag import DAGIterator
from e3.job import Job

logger = e3.log.getLogger("job.scheduler")

# The default maximum duration for a job, in seconds (24 hours).
DEFAULT_JOB_MAX_DURATION = 3600 * 24


class Scheduler(object):
    """Handle parallel execution of interdependent jobs."""

    def __init__(
        self,
        job_provider,
        collect=None,
        queues=None,
        tokens=1,
        job_timeout=DEFAULT_JOB_MAX_DURATION,
    ):
        """Initialize Scheduler.

        :param job_provider: function that returns instances of Job.
            The function takes as arguments: the job uid, the data
            associated with it, the list of predecessors id and and
            a notification function called when the job end.
        :type job_provider: (str, T, list[str], str -> None) -> Job
        :param collect: function that collect results from the
            jobs. If the function returns True then the job is requeued
        :type collect: Job -> bool
        :param queues: describes the list of queues handled by the
            scheduler. The format is a dictionary for which which
            keys are queue names and value the max number of tokens
            available at a given time. if None then a single queue
            called "default" is created. Its size is then given by
            the tokens parameter.
        :type queues: dict(str, int) | None
        :param tokens: number of tokens for the default queue. Relevant
            only when queues is None
        :type tokens: int
        :param job_timeout: maximum execution time for a job. The default
            is 24h. If set to None timeout are disabled but it also make
            the scheduller non interruptable when waiting for a job to
            finish.
        :type job_timeout: int | None
        """
        self.job_provider = job_provider
        self.collect = collect
        self.job_timeout = job_timeout
        if self.collect is None:
            self.collect = lambda x: False

        self.active_jobs = []
        self.queued_jobs = 0
        self.all_jobs_queued = False
        self.message_queue = None
        self.dag = None
        self.dag_iterator = None
        self.start_time = None
        self.stop_time = None
        self.max_active_jobs = 0

        # Initialize named queues
        self.queues = {}
        self.tokens = {}
        self.n_tokens = 0

        if queues is None:
            # If no queues are specificied create a default one
            # with no name.
            queues = {"default": tokens}

        self.global_queue_index = 1

        # Create the queues
        for name, max_token in queues.items():
            self.queues[name] = []
            self.tokens[name] = max_token
            self.n_tokens += max_token

        # Create a slot reserve. The goal is to give a given job a number
        # which is unique among the active jobs. We need a maximum of
        # self.n_tokens slots
        self.slots = list(range(self.n_tokens))

    def safe_collect(self, *args, **kwargs):
        """Protect call to collect.

        This ensures for job such as JobProcess that there are no calls to
        Run during collect. Main goal is to avoid leak of handles from collect
        to a process spawned by a Job. On Unixes consequences of such leak is
        more a security concern than an operational one. On Windows, this can
        lead easily to file locking issues and thus might cause crashes.
        """
        with Job.lock:
            return self.collect(*args, **kwargs)

    def safe_job_provider(self, *args, **kwargs):
        """Protect call to job_provider.

        See safe_collect commment above.
        """
        with Job.lock:
            return self.job_provider(*args, **kwargs)

    @classmethod
    def simple_provider(cls, job_class):
        """Return a simple provider based on a given Job class.

        :param job_class: a subclass of Job
        :type job_class: () -> Job
        """

        def provider(uid, data, predecessors, notify_end):
            del predecessors
            return job_class(uid, data, notify_end)

        return provider

    def init_state(self, dag):
        """Reinitialize the scheduler state (internal function).

        :param dag: the dag representing the list of job to execute
        :type dag: e3.collection.dag
        """
        # Active jobs
        self.active_jobs = []

        # Total number of jobs in the queues
        self.queued_jobs = 0

        # Have all jobs been queued?
        self.all_jobs_queued = False

        # Message queue to get job end notifications
        self.message_queue = Queue()

        self.dag = dag
        self.dag_iterator = DAGIterator(dag, enable_busy_state=True)
        self.start_time = datetime.now()
        self.stop_time = None
        self.max_active_jobs = 0

    @property
    def is_finished(self):
        """Check if all jobs have been executed (internal).

        :return: True if complete
        :rtype: bool
        """
        # The run is considered finished once there is no more job
        # in the DAG, the queues and that no job is running.
        return self.all_jobs_queued and self.queued_jobs == 0 and not self.active_jobs

    def log_state(self):
        """Log the current state of the scheduler (internal)."""
        logger.debug(
            "non-ready?: %s, in queue: %s, running: %s",
            not self.all_jobs_queued,
            self.queued_jobs,
            len(self.active_jobs),
        )

    def run(self, dag):
        """Launch the scheduler.

        :param dag: jobs to be executed
        :type dag: e3.collection.dag
        """
        self.init_state(dag)

        try:
            while not self.is_finished:
                self.enqueue()
                self.launch()
                self.log_state()
                self.max_active_jobs = max(self.max_active_jobs, len(self.active_jobs))
                self.wait()
        except KeyboardInterrupt:
            logger.info("Interrupting jobs...")
            for p in self.active_jobs:
                p.interrupt()
                self.safe_collect(p)
                p.on_finish(self)
            raise KeyboardInterrupt
        self.stop_time = datetime.now()

    def push(self, job):
        """Push a job into a queue.

        :param job: a job
        :type job: Job
        """
        # We use a tuple here to ensure the stability of the queue
        # when two jobs have similar priorities.
        heapq.heappush(
            self.queues[job.queue_name], (-job.priority, self.global_queue_index, job)
        )
        self.global_queue_index += 1
        self.queued_jobs += 1

    def enqueue(self):
        """Push into the queues job that are ready (internal)."""
        if self.all_jobs_queued:
            return

        try:
            while True:
                uid, data, predecessors = self.dag_iterator.next_element()
                if uid is None:
                    # No more jobs ready
                    return

                job = self.safe_job_provider(
                    uid,
                    data,
                    predecessors=predecessors,
                    notify_end=self.message_queue.put,
                )
                if job.should_skip:
                    self.safe_collect(job)
                    job.on_finish(self)
                    self.dag_iterator.leave(uid)
                else:
                    self.push(job)
        except StopIteration:
            self.all_jobs_queued = True

    def launch(self):
        """Launch next jobs in the queues (internal)."""
        if self.queued_jobs == 0:
            return

        for name in self.queues:
            q = self.queues[name]
            while q and q[0][2].tokens <= self.tokens[name]:
                _, _, next_job = heapq.heappop(q)
                self.queued_jobs -= 1
                next_job.on_start(self)
                next_job.start(slot=self.slots.pop())
                self.tokens[name] -= next_job.tokens
                self.active_jobs.append(next_job)

    def wait(self):
        """Wait for the end of an active job."""
        if not self.active_jobs:
            return

        # Wait for message from one the active jobs
        while True:
            # The first job in active jobs is the oldest one
            # compute the get timeout based on its startup information
            first_job = self.active_jobs[0]
            current_timeout = self.job_timeout - first_job.timing_info.duration

            # Ensure waiting time is a positive number
            current_timeout = max(0.1, current_timeout)

            try:
                uid = self.message_queue.get(block=True, timeout=current_timeout)

            except Empty:
                # If after timeout we get an empty result, it means that
                # the oldest job has reached the timeout. Interrupt it
                # and wait for the queue to receive the end notification
                self.active_jobs[0].interrupt()
                time.sleep(0.1)

            else:
                job_index, job = next(
                    (
                        (index, job)
                        for index, job in enumerate(self.active_jobs)
                        if job.uid == uid
                    )
                )
                ti = job.timing_info
                logger.debug(
                    "job %s %s after %s",
                    uid,
                    "interrupted" if job.interrupted else "finished",
                    ti.duration,
                )
                self.slots.append(job.slot)

                # Liberate the resources taken by the job
                self.tokens[job.queue_name] += job.tokens
                collect_result = self.safe_collect(job)
                job.on_finish(self)

                if collect_result:
                    # Requeue when needed
                    self.push(job)
                else:
                    # Mark the job as completed
                    if job.uid in self.dag:
                        self.dag_iterator.leave(job.uid)

                del self.active_jobs[job_index]
                return
