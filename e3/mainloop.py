"""Generic loop for running jobs.

Parallelism, abortion and time control are the key features.

Each MainLoop instance controls a set of Workers whose number is set
by the user. The list of jobs to be achieved by the workers,
is provided by a list. The mainloop distribute the elements to the
the workers when they have nothing to do. Usually, an element is a
string identifying the job to be run. An element can also be a list
in that case the worker will execute sequentially each "subelement".

When a worker is asked to run a job, the command is executed by
calling run_job (worker_id). Once a test is finished the function
collect_result will be called with the worker_id, and process (a
:class:`e3.os_process.Run` object) and the job_info as parameters. Both
run_job and collect_result are user defined functions.

Note also that from the user point view there is no parallelism to handle.
The two user defined function run_job and collect_result are called
sequentially.
"""
from __future__ import absolute_import

import argparse
import os
from time import sleep

import e3.env
import e3.log
from e3.collection.dag import DAG
from e3.os.platform import UNKNOWN

logger = e3.log.getLogger('mainloop')


SKIP_EXECUTION = -1
# Ask the mainloop to stop execution
# See MainLoop documentation


class NeedRequeue(Exception):
    """Raised by collect_result if a job need to be requeued."""
    pass


class TooManyErrors(Exception):
    """Raised by collect_result if there ase too many errors.

    This exception is raised when the number of consecutive errors
    is higher than the value defined by --max-consecutive-failures
    """
    pass


class Worker(object):
    """Run run_job and collect_result."""

    def __init__(self, items, run_job, collect_result, slot):
        """Worker constructor.

        :param items: item or list of items to be run by the worker
        :param run_job: command builder function (see MainLoop doc)
        :param collect_result: result processing function (see MailLoop doc)
        """
        self.run_job = run_job
        self.collect_result = collect_result
        self.slot = slot

        # Count the number of retry for the current job
        self.nb_retry = 0

        if isinstance(items, list):
            items.reverse()
            self.jobs = items
        else:
            self.jobs = [items]

        e3.log.debug('Init worker %d with %r', self.slot, self.jobs)
        self.current_process = None
        self.current_job = None
        self.execute_next()

    def execute_next(self):
        """Execute next worker job.

        :return: False if the worker has nothing to do. True if a test is
          launched.
        :rtype: bool
        """
        if len(self.jobs) == 0:
            return False
        else:
            self.current_job = self.jobs.pop()

            job_info = (self.slot, self.nb_retry)
            self.current_process = self.run_job(self.current_job,
                                                job_info)
            return True

    def poll(self):
        """Test if a job is still executing.

        :return: True if busy, False otherwise.
        :rtype: bool
        """
        if self.current_process == SKIP_EXECUTION:
            # Test not run by run_job
            # Call directly wait()
            self.wait()
            return False
        else:
            if self.current_process.poll() is not None:
                # Current process has finished
                self.wait()
                return False
            else:
                return True

    def wait(self):
        """Wait for a test/item to finish.

        The collect_result function is called upon job termination.
        """
        if self.current_process != SKIP_EXECUTION:
            self.current_process.wait()

        try:
            job_info = (self.slot, self.nb_retry)
            self.collect_result(self.current_job,
                                self.current_process,
                                job_info)
            self.current_job = None
            self.current_process = None

        except NeedRequeue:
            # Reinsert the current job in the job list
            self.nb_retry += 1
            self.jobs.append(self.current_job)


class MainLoop(object):
    """Run a list of jobs."""

    def __init__(self,
                 item_list,
                 run_job,
                 collect_result,
                 parallelism=None,
                 abort_file=None,
                 dyn_poll_interval=True):
        """Launch loop.

        :param item_list: a list of jobs or a dag
        :param run_job: a function that takes a job for argument and
            return the spawned process (:class:`e3.os_process.Run` object).
            Its prototype should be ``func (name, job_info)`` with name the job
            identifier and job_info the related information, passed in a tuple
            (slot_number, job_retry). Note that if you want to take advantage
            of the parallelism the spawned process should be launched in
            background (ie with bg=True when using :class:`e3.os_process.Run`).
            If run_job returns SKIP_EXECUTION instead of a Run object
            the mainloop will directly call collect_result without waiting.
        :param collect_result: a function called when a job is finished. The
            prototype should be func (name, process, job_info). If
            collect_result raise NeedRequeue then the test will be requeued.
            job_info is a tuple: (slot_number, job_nb_retry)
        :param parallelism: number of workers
        :type parallelism: int | None
        :param abort_file: If specified, the loop will abort if the file is
            present
        :type abort_file: str | None
        :param dyn_poll_interval: If True the interval between each polling
            iteration is automatically updated. Otherwise it's set to 0.1
            seconds.
        :type dyn_poll_interval: bool
        """
        e = e3.env.Env()
        self.parallelism = e.get_attr("main_options.mainloop_jobs",
                                      default_value=1,
                                      forced_value=parallelism)
        self.abort_file = e.get_attr("main_options.mainloop_abort_file",
                                     default_value=None,
                                     forced_value=abort_file)

        if self.parallelism == 0:
            if e.build.cpu.cores != UNKNOWN:
                self.parallelism = e.build.cpu.cores
            else:
                self.parallelism = 1

        e3.log.debug("start main loop with %d workers (abort on %s)",
                     self.parallelism, self.abort_file)
        self.workers = [None] * self.parallelism
        self.locked_items = [None] * self.parallelism

        if not isinstance(item_list, DAG):
            self.item_list = DAG(item_list)
        else:
            self.item_list = item_list

        self.iterator = self.item_list.__iter__()
        self.collect_result = collect_result
        active_workers = 0
        max_active_workers = self.parallelism
        poll_sleep = 0.1
        no_free_item = False

        try:
            while True:
                # Check for abortion
                if self.abort_file is not None and \
                        os.path.isfile(self.abort_file):
                    logger.info('Aborting: file %s has been found',
                                self.abort_file)
                    self.abort()
                    return      # Exit the loop

                # Find free workers
                for slot, worker in enumerate(self.workers):
                    if worker is None:
                        # a worker slot is free so use it for next job
                        next_id, next_job = self.iterator.next()
                        if next_job is None:
                            no_free_item = True
                            break
                        else:
                            self.locked_items[slot] = next_id
                            self.workers[slot] = Worker(next_job,
                                                        run_job,
                                                        collect_result,
                                                        slot)
                            active_workers += 1

                poll_counter = 0
                e3.log.debug('Wait for free worker')
                while active_workers >= max_active_workers or no_free_item:
                    # All worker are occupied so wait for one to finish
                    poll_counter += 1
                    for slot, worker in enumerate(self.workers):
                        if worker is None:
                            continue

                        # Test if the worker is still active and have more
                        # job pending
                        if not (worker.poll() or worker.execute_next()):
                            # If not the case free the worker slot
                            active_workers -= 1
                            self.workers[slot] = None
                            self.item_list.release(self.locked_items[slot])
                            no_free_item = False
                            self.locked_items[slot] = None

                    sleep(poll_sleep)

                if dyn_poll_interval:
                    poll_sleep = compute_next_dyn_poll(poll_counter,
                                                       poll_sleep)

        except (StopIteration, KeyboardInterrupt) as e:
            if e.__class__ == KeyboardInterrupt:
                # Got ^C, abort the mainloop
                logger.error("User interrupt")

            # All the jobs are finished
            while active_workers > 0:
                for slot, worker in enumerate(self.workers):
                    if worker is None:
                        continue

                    # Test if the worker is still active and ignore any
                    # job pending
                    try:
                        still_running = worker.poll()
                    except TooManyErrors:
                        still_running = False
                        # We're not spawing more jobs so we can safely
                        # ignore all TooManyErrors exceptions.
                    if not still_running:
                        active_workers -= 1
                        self.workers[slot] = None
                    sleep(0.1)

            if e.__class__ == KeyboardInterrupt:
                self.abort()
                raise

        except TooManyErrors:
            # too many failures, abort the execution
            logger.error("Too many errors, aborting")
            self.abort()

    def abort(self):
        """Abort the loop."""
        # First force release of all elements to ensure that iteration
        # on the remaining DAG elements won't be blocked
        for job_id in self.locked_items:
            if job_id is not None:
                self.item_list.release(job_id)

        # Wait for worker still active if necessary
        if self.abort_file is not None and os.path.isfile(self.abort_file):
            for worker in self.workers:
                if worker is not None:
                    worker.wait()

        # Mark remaining jobs as skipped
        for job_id, job_list in self.iterator:
            self.item_list.release(job_id)
            if not isinstance(job_list, list):
                job_list = [job_list]
            for job in job_list:
                self.collect_result(job, SKIP_EXECUTION, None)


def compute_next_dyn_poll(poll_counter, poll_sleep):
    """Adjust the polling delay."""
    # if two much polling is done, the loop might consume too
    # much resources. In the opposite case, we might wait too
    # much to launch new jobs. Adjust accordingly.
    if poll_counter > 8 and poll_sleep < 1.0:
        poll_sleep *= 1.25
        e3.log.debug('Increase poll interval to %f', poll_sleep)
    elif poll_sleep > 0.0001:
        poll_sleep *= 0.75
        e3.log.debug('Decrease poll interval to %f', poll_sleep)
    return poll_sleep


def mainloop_argument_parser():
    """Add command line arguments to control mainloop default."""

    argument_parser = argparse.ArgumentParser()
    mgroup = argument_parser.add_argument_group(
        title='Mainloop control')
    mgroup.add_option(
        '-j', '--jobs',
        dest='mainloop_jobs',
        type='int',
        metavar='N',
        default=1,
        help='Specify the number of jobs to run simultaneously')
    mgroup.add_option(
        '--abort-file',
        dest='mainloop_abort_file',
        metavar='FILE',
        help='Specify a file whose presence cause loop abortion')
    return argument_parser
