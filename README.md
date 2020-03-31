The `e3` Project
================

[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/979/badge)](https://bestpractices.coreinfrastructure.org/projects/979)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![Documentation Status](https://readthedocs.org/projects/e3-core/badge/?version=latest)](http://e3-core.readthedocs.io/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/AdaCore/e3-core/branch/master/graph/badge.svg)](https://codecov.io/gh/AdaCore/e3-core)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

This present project (`e3`) is a Python framework to ease the development
of portable automated build systems (compilation, dependencies management,
binary code packaging, and automated testing).

The `e3` framework is split across multiple Python packages named `e3-<name>`
and sharing the same namespace: `e3`.

Code status
===========

Platform | Status
---------|-------
Linux    | [![Build Status](https://travis-ci.org/AdaCore/e3-core.svg?branch=master)](https://travis-ci.org/AdaCore/e3-core)
Windows  | [![Build status](https://ci.appveyor.com/api/projects/status/c8lgr7t0pmg1q89f/branch/master?svg=true)](https://ci.appveyor.com/project/github-integration-adacore/e3-core/branch/master)


`e3-core` content
=================

`e3-core` package is organized in several packages and modules:

- *anod*: build system handling dependencies management and binary code
  packaging. This includes a driver that can parse `.anod` specification
  files.
- *archive*: support for reading and writing tar and zip archives
- *collection*: generic collections, e.g. an implementation of Direct Acyclic
  Graphs
- *decorator*: Python decorators, e.g. a memoize decorator
- *diff*: functions to compute a diff or apply it
- *electrolyt*: support for parsing build plans
- *env*: global environment handling
- *error*: `e3` exceptions
- *event*: interface for notifying external services
- *fingerprint*: support for creating a synthetic view of set of
  conditions and determining whether those conditions have changed
  or not.
- *fs*: high-level file system operations, using globbing, walk,...
- *hash*: computation of sha1, md5
- *log*: logging helpers
- *main*: main program initialization, command line parsing,...
- *mainloop*: generic loop for running jobs
- *net*: network utilities
  - *net.http*: helper for sending http requests and downloading files
  - *net.smtp*: helper for sending emails through smtp
- *os*: platform independent interface to Operating System functions
  - *os.fs*: low-level file system operations, no logging involved
  - *os.platform*: tools to detect the platform
  - *os.process*: interface to run process, to control the execution time,...
  - *os.timezone*: platform independent interface to get the machine timezone
- *platform*: generic interface for providing platform information
- *platform_db*: knowledge base for computing platform information
- *store*: interface to download and store resources in a store
- *sys*: `e3` information, sanity check, ...
- *text*: text formatting and transformation
- *vcs*: high level interface to VCS repositories
- *yaml*: helpers for parsing yaml data

See [e3-core documentation](http://e3-core.readthedocs.io/en/latest/) for
more details.


Install
=======

requires: Python >=3.7

e3-core releases are available on PyPI and can be installed by running:

```bash
pip install e3-core
```

To install from the source package, run:

```bash
python setup.py install
```

All `e3` dependencies will also be installed.

Contributing
============

See [CONTRIBUTING.md](CONTRIBUTING.md).
