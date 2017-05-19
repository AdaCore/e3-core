from __future__ import absolute_import, division, print_function

import e3.log
from e3.job import Job
from e3.job.scheduler import Scheduler

logger = e3.log.getLogger('electrolyt.exec')


FORCE_SKIP = -125
FORCE_FAIL = -126
STATUS_UNKNOWN = -127


class ElectrolytJob(Job):

    def __init__(self, uid, data, notify_end, sandbox,
                 force_status=STATUS_UNKNOWN):
        Job.__init__(self, uid, data, notify_end)
        self.status = force_status
        self.sandbox = sandbox

    def run(self):
        if self.status == STATUS_UNKNOWN:
            for class_name in [
                    k.__name__ for k in self.data.__class__.__mro__]:
                method_name = 'do_%s' % class_name.lower()
                if hasattr(self, method_name):
                    getattr(self, method_name)()


class ElectrolytJobFactory(object):

    def __init__(self, sandbox, asr):
        self.job_status = {}
        self.sandbox = sandbox
        self.asr = asr

    def get_job(self, uid, data, predecessors, notify_end):
        force_fail = any((k for k in predecessors
                          if self.job_status[k] not in (0, 125, FORCE_SKIP)))
        return ElectrolytJob(
            uid,
            data,
            notify_end,
            sandbox=self.sandbox,
            force_status=STATUS_UNKNOWN if not force_fail else FORCE_FAIL)

    def collect(self, job):
        self.job_status[job.uid] = job.status
        logger.info("%-48s [queue=%-10s status=%3d]" %
                    (job.data, job.queue_name,
                     self.job_status[job.uid]))

    def run(self, action_list):
        sch = Scheduler(self.get_job, self.collect)
        sch.run(action_list)
