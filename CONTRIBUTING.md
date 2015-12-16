The `e3-core` package
=====================

Code conventions
----------------

All code should follow [PEP8](https://www.python.org/dev/peps/pep-0008/)
(the only exception is `e3/platform_db.py`). We also expect that
[PyFlakes](https://pypi.python.org/pypi/pyflakes) has been run before sending
a patch.

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

Testing
-------

requires: [tox](https://pypi.python.org/pypi/tox)
If not already installed, install it via:

```bash
pip install tox
```

In order to run the public testsuite of `e3-core`, do:

```bash
tox
```
