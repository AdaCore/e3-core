from __future__ import absolute_import, division, print_function

import e3.log
from e3.job import Job
from e3.job.scheduler import Scheduler
from e3.anod.status import ReturnValue

logger = e3.log.getLogger('electrolyt.exec')
STATUS = ReturnValue

class ElectrolytJob(Job):

    def __init__(self, uid, data, notify_end, sandbox, store,
                 force_status=STATUS.STATUS_UNKNOWN,
                 dry_run=False):
        """Initialize the context of the job.

        :param uid: uid of the job
        :type uid: str
        :param data: object to be processed by the job
        :type data: child of e3.anod.action.Action
        :param notify_end: callback to call when job is finished
        :type notify_end: function
        :param sandbox: current working sandbox
        :type sandbox: e3.anod.sandbox.SandBox
        :param force_status: set the status of the job
        :type force_status: e3.anod.status.ReturnValue
        :param dry_run: if True report kind of action without execution
        :param dry_run: bool
        """
        Job.__init__(self, uid, data, notify_end)
        self.status = force_status
        self.sandbox = sandbox
        self.dry_run = dry_run
        self.store = store

    def run(self):
        if self.status == STATUS.STATUS_UNKNOWN:
            for class_name in [
                    k.__name__ for k in self.data.__class__.__mro__]:
                method_name = 'do_%s' % class_name.lower()
                if self.dry_run:
                    return
                if hasattr(self, method_name):
                    getattr(self, method_name)()


class ElectrolytJobFactory(object):

    def __init__(self, sandbox, asr, store, dry_run=False):
        self.job_status = {}
        self.sandbox = sandbox
        self.asr = asr
        self.dry_run = dry_run
        self.store = store

    def get_job(self, uid, data, predecessors, notify_end):
        force_fail = any((k for k in predecessors
                          if self.job_status[k] not in (STATUS.success,
                                                        STATUS.FORCE_SKIP,
                                                        STATUS.FORCE_SKIP)))
        return ElectrolytJob(
            uid,
            data,
            notify_end,
            sandbox=self.sandbox,
            store = self.store,
            force_status=STATUS.STATUS_UNKNOWN if not force_fail else STATUS.failure,
            dry_run = self.dry_run)

    def collect(self, job):
        self.job_status[job.uid] = job.status
        logger.info("%-48s [queue=%-10s status=%3d]" %
                    (job.data, job.queue_name,
                     self.job_status[job.uid].value))

    def run(self, action_list):
        sch = Scheduler(self.get_job, self.collect)
        sch.run(action_list)
