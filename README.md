The `e3` Project 
================

This present project (`e3`) is a Python framework to ease the development
of portable automated build systems (compilation, dependencies management,
binary code packaging, and automated testing).

The `e3` framework is split across multiple Python packages named `e3-<name>`
and sharing the same namespace: `e3`.

Code status
===========

Platform | Status
---------|-------
Linux    | [![Build Status](https://travis-ci.org/AdaCore/e3-core.svg?branch=master)](https://travis-ci.org/AdaCore/e3-core) [![Coverage Status](https://coveralls.io/repos/github/AdaCore/e3-core/badge.svg?branch=master)](https://coveralls.io/github/AdaCore/e3-core?branch=master)
Windows  | [![Build status](https://ci.appveyor.com/api/projects/status/c8lgr7t0pmg1q89f/branch/master?svg=true)](https://ci.appveyor.com/project/github-integration-adacore/e3-core/branch/master)

`e3-core` content
=================

`e3-core` package is organized in several packages and modules:

- *anod*: build system handling dependencies management and binary code
  packaging. This includes a driver that can parse `.anod` specification
  files.
- *archive*: support for reading and writing tar and zip archives
- *binarydata*: helpers for parsing binary data such as object files,
  executables, …
- *collection*: generic collections, e.g. an implementation of Direct Acyclic
  Graphs
- *decorator*: Python decorators, e.g. a memoize decorator
- *diff*: functions to compute a diff or apply it
- *electrolyt*: support for parsing build plans
- *env*: global environment handling
- *error*: `e3` exceptions
- *event*: interface for notifying external services
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


Install
=======

requires: Python 2.7.x (experimental support of Python >=3.4)

To install `e3`, run:

```bash
python setup.py install
```

All `e3` dependencies will also be installed.

Contributing
============

See [CONTRIBUTING.md](CONTRIBUTING.md).
