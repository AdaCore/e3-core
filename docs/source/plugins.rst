.. _plugin:

Using abc and stevedore to write plugins
========================================

Introduction
------------

``e3-core`` is designed to be small and to be easy to configure and extend by
loading external code dynamically. In order to discover and load the plugins at runtime ``e3-core`` uses setuptools entry points. To ease the management of the plugins and avoid hard to detect errors, the ``e3`` project uses ``stevedore`` and ``abc``.

An entry point is a way to reference an object defined in another Python package.
In ``e3`` these objects are classes derived from an abstract base class (using ``abc``) defining the plugin interface.

Namespaces
----------

The namespace for ``e3`` entry point are all prefixed with ``e3.`` in order to
avoid polluting the namespace.

e3-core plugins
---------------

``e3-core`` defines and uses the following plugins interface:

e3-sandbox
^^^^^^^^^^

The command line actions for ``e3-sandbox`` can be provided by external plugins registered in the ``e3.anod.sandbox.sandbox_action`` namespace.
To add another action subclass :class::`e3.anod.sandbox.SandBoxAction` and
reference your new class in the ``e3.anod.sandbox.sandbox_action`` entry points namespace.

Example
"""""""

In a package ``e3-contrib``, define a new class:

.. code-block:: python

   class SandBoxActionExample(e3.anod.sandbox.SandBoxAction):

       name = 'example'
       help = 'An example of e3-sandbox action'

       def add_parser(self):
           self.parser.add_argument(
               '--another-command-line')

       def run(self.args):
           sandbox = e3.anod.sandbox.SandBox()
           sandbox.root_dir = args.sandbox

           # Run any action on the sandbox
           # ...

Then register it in ``e3-contrib/setup.py``:

.. code-block:: python

       entry_points={
           'e3.anod.sandbox.sandbox_action': [
               'example = e3.contrib.sandbox.SandBoxActionExample',
       ]}
