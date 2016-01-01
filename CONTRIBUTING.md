The `e3-core` package
=====================

Code conventions
----------------

All code should follow [PEP8](https://www.python.org/dev/peps/pep-0008/).
We also expect that [PyFlakes](https://pypi.python.org/pypi/pyflakes) has been
run before sending a patch.

All logging done by `E3` must be done via a logger returned by the function
`e3.log.getLogger`. Very verbose logging can be achieved by adding calls to
`e3.log.debug()`. This will be activated when an application using
`e3.main.Main` is run with: `-v -v`.

All entry points must instanciate `e3.main.Main` to parse their options.

Exceptions raised by `E3` should derived from `e3.error.E3Error`.

All import used in `E3` should be _absolute imports_. To force this, we add at
the beginning of each `E3` module:

```python
from __future__ import absolute_import
```

The `e3` namespace
------------------

The `e3` framework provides a namespace package. It allows creating
separated packages living under the `e3` namespace.

Such a package must:

   * define an `e3/__init__.py` file containing **only**:

     ```python
     __import__('pkg_resources').declare_namespace(__name__)
     ```

   * set to `e3` the value of the *namespace package* argument
     of the setup() function of its ``setup.py`` (see [setup.py](setup.py)).

See [setuptools namespace-packages doc][1] for more info.

[1]: http://pythonhosted.org/setuptools/setuptools.html#namespace-packages

Plugin system
-------------

`e3` uses a plugin system based on
[stevedore][https://github.com/openstack/stevedore] built on top of setuptools
entry points. `e3-core` is meant to be as small as possible and extented with
plugins.

To add a new feature based on plugins, first define a base class with
[abc (Abstract Base Classes)][https://docs.python.org/2/library/abc.html] that
will implement the plugin interface. Other packages can then create plugin by
deriving the base class (the interface) and referencing the entry point in its
``setup.py``. `e3-core` can then use the plugin via `stevedore`. See the
[plugin system documentation](docs/plugin.rst).

Testing
-------

requires: [tox](https://pypi.python.org/pypi/tox)
If not already installed, install it via:

```bash
pip install tox
```

In order to run the public testsuite of `e3-core` and check that there
is no error when generating the documentation, do:

```bash
tox
```

The doc is generated in ``.tox/docs/html``.

To verify that the `e3-core` package is PEP8 compliant and that no error is
reported by PyFlakes, do:

```bash
tox -e checkstyle
```

You can also verify the experimental support of Python 3 by running:

```bash
tox -e py34
```

All Python 2 code is converted to Python 3 using `2to3`.
