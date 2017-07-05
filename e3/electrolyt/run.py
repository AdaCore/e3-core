from __future__ import absolute_import, division, print_function

import os
import sys
import traceback

import e3.log
from e3.anod.driver import AnodDriver
from e3.anod.status import ReturnValue
from e3.fs import sync_tree
from e3.job import Job
from e3.job.scheduler import Scheduler
from e3.vcs.git import GitRepository

logger = e3.log.getLogger('electrolyt.exec')
STATUS = ReturnValue


class ElectrolytJob(Job):

    def __init__(self, uid, data, notify_end, sandbox, store,
                 force_status=STATUS.status_unknown,
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
        super(ElectrolytJob, self).__init__(uid, data, notify_end)
        self.status = force_status
        self.sandbox = sandbox
        self.dry_run = dry_run
        self.store = store

    def run(self):
        if self.status == STATUS.status_unknown and not self.dry_run:
            try:
                getattr(self, self.data.run_method)()
            except Exception as e:
                self.status = STATUS.failure
                logger.error(
                    'Exception occurred in action %s %s',
                    self.data.run_method, e)
                _, _, exc_traceback = sys.exc_info()
                logger.error(traceback.format_tb(exc_traceback))

    def run_anod_primitive(self, primitive=None):
        """Run an anod primitive after setting up the sandbox."""
        self.data.anod_instance.sandbox = self.sandbox
        anod_driver = AnodDriver(anod_instance=self.data.anod_instance,
                                 store=self.store)
        anod_driver.activate()
        anod_driver.anod_instance.build_space.create(quiet=True)
        getattr(anod_driver.anod_instance, primitive)()
        self.status = STATUS.success

    def do_build(self):
        """Run anod build primitive."""
        return self.run_anod_primitive('build')

    def do_install(self):
        """Run anod install primitive."""
        return self.run_anod_primitive('install')

    def do_test(self):
        """Run anod test primitive."""
        return self.run_anod_primitive('test')

    def do_checkout(self):
        """Get sources from vcs to sandbox vcs_dir."""
        repo_name = self.data.repo_name
        repo_url = self.data.repo_data['url']
        repo_revision = self.data.repo_data['revision']
        repo_vcs = self.data.repo_data['vcs']
        if repo_vcs != 'git':
            logger.error('%s vcs type not supported', repo_vcs)
            self.status = STATUS.failure
            return
        repo_dir = os.path.join(self.sandbox.vcs_dir, repo_name)
        g = GitRepository(repo_dir)
        if e3.log.default_output_stream is not None:
            g.log_stream = e3.log.default_output_stream
        g.init()
        g.update(repo_url, repo_revision, force=True)
        self.status = STATUS.success

    def do_createsource(self):
        """Prepare src from vcs to cache using sourcebuilders."""
        source_name = self.data.source_name
        tmp_cache_dir = os.path.join(self.sandbox.tmp_dir, 'cache')
        src = self.sandbox.vcs_dir
        for src_builder in self.data.anod_instance.source_pkg_build:
            if src_builder.name == source_name:
                repo_dict = {}
                src_dir = os.path.join(src, src_builder.checkout[0])
                dest_dir = os.path.join(tmp_cache_dir, source_name)
                # ??? missing repository state
                repo_dict[source_name] = {"working_dir": src_dir}
                src_builder.prepare_src(repo_dict, dest_dir)
                self.status = STATUS.success
                logger.debug('%s created in cache/tmp', source_name)
                return

    def do_getsource(self):
        """action_item from an intermediate node.

        This action should return success status so do_install
        source can procede.
        """
        self.status = STATUS.success

    def do_installsource(self):
        """Install the source from tmp/cache to build_space/src."""
        spec = self.data.spec
        spec.sandbox = self.sandbox
        anod_instance = AnodDriver(anod_instance=spec, store=self.store)
        anod_instance.activate()
        source = self.data.source
        src_dir = os.path.join(self.sandbox.tmp_dir,
                               'cache',
                               source.name)
        dest_dir = os.path.join(spec.build_space.src_dir)
        sync_tree(src_dir, dest_dir, ignore=source.ignore)
        self.status = STATUS.success

    def do_root(self):
        """Express the final result of the exec."""
        # This method won't be executed unless all the predecessor jobs are
        # successful, so it will just report success state
        self.status = STATUS.success
        logger.info('result: OK')


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
                                                        STATUS.force_skip)))
        return ElectrolytJob(
            uid,
            data,
            notify_end,
            sandbox=self.sandbox,
            store=self.store,
            force_status=(STATUS.status_unknown
                          if not force_fail
                          else STATUS.failure),
            dry_run=self.dry_run)

    def collect(self, job):
        self.job_status[job.uid] = job.status
        logger.info("%-48s [queue=%-10s status=%03d]" %
                    (job.data, job.queue_name,
                     self.job_status[job.uid].value))

    def run(self, action_list):
        sch = Scheduler(self.get_job, self.collect)
        sch.run(action_list)
