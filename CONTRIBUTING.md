Contributing
============

Feedback and pull-requests
--------------------------

For feature requests, bug reports, vulnerability reports, and feedback, please
provide them as GitHub issues.

To submit a patch please create a pull request from your topic branch.
You should create a separate branch for each single topic (bug fix or
new feature). Please follow commit message guideline from
[git-scm book](http://git-scm.com/book/ch5-2.html). Try to break several
logical changes or bug fixes in several commits.

We also ask you to sign our [Contributor Licence Agreement](https://github.com/AdaCore/contributing-howto).

Code conventions
----------------

### PEP8, PEP257, Pyflakes, and Black

All code should follow [PEP8](https://www.python.org/dev/peps/pep-0008/),
[PEP257](https://www.python.org/dev/peps/pep-0257/).

You should also document your method's parameters and their return values
in *reStructuredText* format:

```python
"""Doc string for function

:param myparam1: description for param1
:param myparam2: description for param1
:return: description for returned object
"""
```

We also expect that [PyFlakes](https://pypi.python.org/pypi/pyflakes) has been
run before sending a patch.

The code is automatically formatted with Black.

### logger

All logging done by `e3` must be done via a logger returned by the function
`e3.log.getLogger`. Very verbose logging can be achieved by adding calls to
`e3.log.debug()`. This will be activated when an application using
`e3.main.Main` is run with: `-v -v`.

### Main

All entry points must instanciate `e3.main.Main` to parse their options.

### Exceptions

Exceptions raised by `e3` should derived from `e3.error.E3Error`.

### hasattr()

Don't use hasattr() - this swallows exceptions and makes debugging much
harder. Use getattr() instead.


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
[stevedore](https://github.com/openstack/stevedore) built on top of setuptools
entry points. `e3-core` is meant to be as small as possible and extented with
plugins.

To add a new feature based on plugins, first define a base class with
[abc (Abstract Base Classes)](https://docs.python.org/2/library/abc.html) that
will implement the plugin interface. Other packages can then create plugin by
deriving the base class (the interface) and referencing the entry point in its
``setup.py``. `e3-core` can then use the plugin via `stevedore`. See the
[plugin system documentation](https://github.com/AdaCore/e3-core/wiki/Plugins).

Documentation
-------------

All public API methods must be documented.

`e3-core` documentation is available in the [e3-core GitHub wiki](https://github.com/AdaCore/e3-core/wiki).

Testing
-------

All features or bug fixes must be tested.

Requires: [tox](https://pypi.python.org/pypi/tox)
If not already installed, install it via:

```bash
pip install tox
```

In order to run the public testsuite of `e3-core`, do:

```bash
tox
```

To verify that the `e3-core` package is PEP8 compliant and that no error is
reported by PyFlakes, do:

```bash
tox -e checkstyle
```

You can also verify the experimental support of Python 3 by running:

```bash
tox -e py34
```

Coverage
--------

The code needs to be covered as much as possible. We're aiming for 100%
coverage. If something cannot be tested on a platform add `no cover`
instruction in the code. This should be done for all platform specific code or for
defensive code that should never be executed. See the file `tests/coverage_<platform>.rc` for patterns to use in order to exclude some line from the coverage report.
