from __future__ import absolute_import

import imp
import inspect

#  from e3.decorator import memoize
from e3.anod.error import SandBoxError

import e3.hash
import e3.log

import os


# Helper for Anod spec, to initialize set the sandbox path so that Anod specs
# can just call, spec(<name>)
sandbox = None


# Keep a reference on all already loaded modules so that we don't start
# garbage collecting the module code when still using the Anod specs
loaded_modules = {}


class AnodModule(object):

    def __init__(self, name, from_sandbox):
        self.name = name
        self.sandbox = from_sandbox
        self.path = os.path.join(from_sandbox.spec_dir, name + '.anod')
        self.anod_module = None
        self.anod_class = None

    def load(self):
        e3.log.debug('loading build spec: %s', self.path)
        if not os.path.exists(self.path):
            raise SandBoxError('the spec %s does not exist' % self.path,
                               'load')

        # Create a new module
        mod_name = 'anod_' + self.name
        self.anod_module = imp.new_module(mod_name)

        with open(self.path) as fd:
            code = compile(fd.read(), self.path, 'exec')
            exec code in self.anod_module.__dict__

        # Compute module checksum, it will be used to track
        # changes and force rebuild. Added in _checksum attribute
        # of the Anod subclass.

        checksum = e3.hash.sha1(self.path)

        # At this stage we have loaded completely the module. Now we need to
        # look for a subclass of Anod. Use python inspection features to
        # achieve this.

        for members in inspect.getmembers(self.anod_module):
            _, value = members
            # Return the first subclass of Anod defined in this module
            if inspect.isclass(value) and value.__module__ == mod_name \
                    and 'Anod' in [k.__name__ for k in value.__mro__]:
                # This class is a child of Anod so register it.
                # Note that even if we won't use directly the
                # module we need to keep a reference on it in order
                # to avoid garbage collector issues.
                value._checksum = checksum

                # Give a name to our Anod class: the basename of the
                # anod spec file (without the .anod extension)
                value.name = self.name

                # Give the current sandbox configuration to our Anod class
                value.sandbox = self.sandbox
                self.anod_class = value
                return

        raise SandBoxError('cannot find Anod subclass in %s' % self.path,
                           'load')


def spec(name, from_sandbox=None):
    """Load an Anod spec class.

    Note that two spec having the same name cannot be loaded in the same
    process as e3 keeps a cache of loaded spec using the spec basename as a
    key.
    :param name: name of the spec to load
    :type name:  str
    :param from_sandbox: sandbox object
    :type from_sandbox: e3.anod.sandbox.SandBox | None

    :return: and Anod class
    """
    if name in loaded_modules:
        return loaded_modules[name].anod_class

    if from_sandbox is None:
        from_sandbox = sandbox

    assert from_sandbox.spec_dir is not None

    module = AnodModule(name, from_sandbox)
    module.load()

    # Register the new module
    loaded_modules[name] = module

    # and return the new class
    return module.anod_class
