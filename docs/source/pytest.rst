Using the e3 pytest plugin
==========================

Introduction
------------

``e3-core`` contains a ``pytest`` plugin that is discovered automatically when
installed. The plugin provides several features: it generates a results file
compatible with anod when the environment variable ``RESULTS_DIR`` is defined.
It provides a simple setup for running coverage (on top of the pytest-cov
plugin). And it provides a env_protect fixture that is automatically activated.


Activating e3-core pytest plugins
---------------------------------

To activate the e3-core pytest plugin, you need to install e3-core and pass
the option ``--e3`` to pytest.

env_protect
^^^^^^^^^^^

When activated, the plugin will register the ``env_protect`` feature to ensure
that all tests are run in isolation. All changes to the environment done in
each test won't impact other tests. Also, each test is run in a separate temp
directory, you won't have to cleanup the files that the tests create.

``env_protect`` also sets some environment variables such as:

* ``TZ=UTC`` to ensure a consistent timezone handling
* ``E3_ENABLE_FEATURE=""`` to discard any specific features supported by e3
* ``E3_CONFIG=/dev/null`` to avoid having a specific e3 config read by the tests

And the e3 DEBUG log level is activated for each tests.

Coverage
^^^^^^^^

When running pytest with ``--e3`` and ``--cov`` options, pytest will
automatically generate an exclude list for lines matching the following
patterns:

* ``all: no cover``
* ``if TYPE_CHECKING:``
* ``@abstractmethod``
* ``# os-specific``
* ``defensive code``
* ``assert_never(),``

And ``<os>-only`` with ``<os>`` different from the local OS, so if you're
running a test on Linux, ``windows-only`` and ``darwin-only`` will be discared.

The opposite ``<os>: no cover`` is also supported.

Specific test for the windows platform are also detected:

* ``if sys.platform == win32``
* ``if sys.platform != win32``
* ``unix-only``

You can also skip complete files by creating an ``omit file`` in
``tests/coverage/omit-file-<os>``. The file should contain a filename per line.

Finally, the option ``--e3-cov-rewrite <origin> <dest>`` changes the paths
reported by coverage. If you run ``--e3-cov-rewrite
.tox/py311/cov-xdist/lib-site-packages src`` instead of seeing reports of files in
``.tox/py311-cov-xdist/lib/site-packages/e3/`` the report will show files
in the repository ``src/e3/``.

``require_tool`` fixture
------------------------

``e3.pytest`` provides a function ``require_tool`` that generates a fixture
allowing to skip tests if a tool is missing. For instance, to create a fixture
that will skip tests if ``git`` is not installed run:

.. code-block:: python

   from e3.pytest import require_tool

   git = require_tool("git")

   # Use it in a test that will run only if git is installed
   def test_git_fixture(git):
       ...
