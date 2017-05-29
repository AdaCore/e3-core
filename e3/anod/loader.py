from __future__ import absolute_import, division, print_function

import imp
import inspect
import os
import sys

import e3.hash
import e3.log
from e3.anod.error import SandBoxError
from e3.fs import ls

logger = e3.log.getLogger('anod.loader')


class AnodSpecRepository(object):
    """Anod spec repository.

    The object represent a set of anod specifications along with their data
    files.
    """

    def __init__(self, spec_dir, spec_config=None):
        """Initialize an AnodSpecRepository.

        :param spec_dir: directory containing the anod specs.
        :type spec_dir: str
        :param spec_config: dictionary containing the configuration for this
            AnodSpecRepository
        :type spec_config: dict
        """
        logger.debug('initialize spec repository (%s)', spec_dir)

        if not os.path.isdir(spec_dir):
            raise SandBoxError(
                'spec directory %s does not exist' % spec_dir)
        self.spec_dir = spec_dir
        self.api_version = None
        self.specs = {}
        self.repos = {}

        # Look for all spec files and data files
        spec_list = {os.path.basename(k)[:-5]: {'path': k, 'data': []}
                     for k in ls(os.path.join(self.spec_dir, '*.anod'),
                                 emit_log_record=False)}
        logger.debug('found %s specs', len(spec_list))

        data_list = [os.path.basename(k)[:-5] for k in
                     ls(os.path.join(self.spec_dir, '*.yaml'),
                        emit_log_record=False)]
        logger.debug('found %s yaml files', len(data_list))

        # Match yaml files with associated specifications
        for data in data_list:
            candidate_specs = [spec_file for spec_file in spec_list
                               if data.startswith(spec_file)]
            # We pick the longuest spec name
            candidate_specs.sort(key=lambda x: len(x))
            if candidate_specs:
                spec_list[candidate_specs[-1]]['data'].append(data)

        # Create AnodModule objects
        for name, value in spec_list.iteritems():
            self.specs[name] = AnodModule(name, **value)

        # Declare spec prolog
        prolog_file = os.path.join(spec_dir, 'prolog.py')
        self.prolog_dict = {'spec_config': spec_config,
                            '__spec_repository': self}
        if os.path.exists(prolog_file):
            with open(prolog_file) as f:
                exec(compile(f.read(), prolog_file, 'exec'),
                     self.prolog_dict)

    def __contains__(self, item):
        """Check by name if a spec is present in the repository.

        :return: True if present, False otherwise
        :rtype: bool
        """
        return item in self.specs and self.specs[item].module is not None

    def load_all(self, ignore_errors=False):
        """Load all the specs present in the repository.

        :param ignore_errors: if True don't stop on error.
        :type ignore_errors: bool
        """
        for name in self.specs:
            try:
                self.specs[name].load(self)
            except SandBoxError:
                if not ignore_errors:
                    raise

    def load(self, name):
        """Load an anod spec.

        :param name: name of the spec to load
        :type name: str
        """
        assert name in self.specs, "spec %s not found" % name
        return self.specs[name].load(self)


class AnodModule(object):

    def __init__(self, name, path, data):
        """Initialize an AnodModule instance.

        :param name: module name
        :type name: str
        :param path: path to the spec
        :type path: str
        :param data: list of data files (yaml files) associated with the spec
        :type data: list[str]
        """
        self.name = name
        self.data = data
        self.path = path
        self.module = None
        self.anod_class = None
        self.checksum = e3.hash.sha1(self.path)

    @property
    def is_loaded(self):
        """Check if a spec is already loaded.

        :return: True if the spec is already loaded, False otherwise
        :rtype: bool
        """
        return self.module is not None

    def load(self, repository):
        """Load an anod specification.

        :param repository: the anod spec repository of the spec file
        :type repository: AnodSpecRepository
        :raise SandBoxError: in case of failure
        """
        if self.is_loaded:
            return self.anod_class

        logger.debug('loading anod spec: %s', self.name)

        # Create a new module
        mod_name = 'anod_' + self.name
        anod_module = imp.new_module(mod_name)

        try:
            with open(self.path) as fd:
                # Inject the prolog into the new module dict
                anod_module.__dict__.update(repository.prolog_dict)

                # Exec spec code
                code = compile(fd.read(), self.path, 'exec')
                exec(code, anod_module.__dict__)
        except Exception as e:
            logger.error('exception: %s', e)
            logger.error('cannot load code of %s', self.name)
            raise SandBoxError(
                origin='load',
                message='invalid spec code for %s' % self.name), \
                None, sys.exc_traceback

        # At this stage we have loaded completely the module. Now we need to
        # look for a subclass of Anod. Use python inspection features to
        # achieve this.

        for members in inspect.getmembers(anod_module):
            _, value = members
            # Return the first subclass of Anod defined in this module
            if inspect.isclass(value) and value.__module__ == mod_name \
                    and 'Anod' in [k.__name__ for k in value.__mro__]:
                # This class is a child of Anod so register it.
                # Note that even if we won't use directly the
                # module we need to keep a reference on it in order
                # to avoid garbage collector issues.
                value.spec_checksum = self.checksum

                # Give a name to our Anod class: the basename of the
                # anod spec file (without the .anod extension)
                value.name = self.name
                self.anod_class = value
                self.module = anod_module
                self.anod_class.data_files = self.data
                self.anod_class.spec_dir = os.path.dirname(self.path)
                return self.anod_class

        logger.error('spec %s does not contains an Anod subclass', self.name)
        raise SandBoxError('cannot find Anod subclass in %s' % self.path,
                           'load')


def spec(name):
    """Load an Anod spec class.

    Note that two spec having the same name cannot be loaded in the same
    process as e3 keeps a cache of loaded spec using the spec basename as a
    key.
    :param name: name of the spec to load
    :type name:  str

    :return: and Anod class
    """
    spec_repository = None
    for k in inspect.stack()[1:]:
        if '__spec_repository' in k[0].f_globals:
            spec_repository = k[0].f_globals['__spec_repository']
            break

    return spec_repository.load(name)
