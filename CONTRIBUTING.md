E3 core
=======

Code conventions
----------------

All code should follow _PEP8_ (the only exception is `e3/platform_db.py`). We
also expect that _PyFlakes_ has been run before sending a patch.

All logging done by E3 must be done via a logger returned by the function
`e3.log.getLogger`. Very verbose logging can be achieved by adding calls to
`e3.log.debug()`. This will be activated when an application using
`e3.main.Main` is run with: `-v -v`.

All entry points must instanciate `e3.main.Main` to parse their options.

Exceptions raised by E3 should derived from `e3.error.E3Error`.

All import used in E3 should be _absolute imports_. To force this, we add:

```python
from __future__ import absolute_import
```

at the beginning of each E3 module.


E3 namespace
------------

E3 provides a namespace package. It allows creating separated packages that
live in the `e3` namespace package. Each package living in the `e3` namespace
package must define a `e3/__init__.py` file containing only:

```python
__import__('pkg_resources').declare_namespace(__name__)
```

And in [setup.py](setup.py) the namespace package argument to setup() defines
the namespace `e3`.

See [setuptools namespace-packages doc][1] for more info.

[1]: http://pythonhosted.org/setuptools/setuptools.html#namespace-packages

Testing
-------

To test E3, just run: `tox`. If it is not already installed, install it via:

```bash
pip install tox
```
