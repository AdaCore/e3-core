E3 core
-------

E3 is a python framework to ease development of testsuites and build
infrastructure in a portable way.

The E3 framework is splitted across multiple Python packages named `e3-<name>`
and sharing the same namespace: `e3`.

Core content
------------

E3 core libary is splitted into several packages and modules:

- archive: support for reading and writing tar and zip archives
- binarydata: helpers for parsing binary data such as object files,
  executables, …
- collection: generic collections, e.g. an implementation of Direct Acyclic
  Graphs
- decorator: python decorators, e.g. a memoize decorator
- diff: functions to compute a diff or apply it
- env: global environment handling
- error: E3 exceptions
- fs: high-level file system operations, using globbing, walk, ...
- hash: computation of sha1, md5
- log: logging helpers
- main: main program initialization, command line parsing, ...
- mainloop: generic loop for running jobs
- net: network utilities
  - net.smtp: helper for sending an email
- os: platform independent interface to OS functions
  - os.fs: low-level file system operations, no logging involved
  - os.platform: tools to detect the platform
  - os.process: interface to run process, control the execution time, ...
  - os.timezone: platform independent interface to get the machine timezone
- platform: generic interface for providing platform information
- platform_db: knowledge base for computing platform information
- sys: E3 information, sanity check, ...
- text: text formatting and transformation
- yaml: helpers for parsing yaml data


Install
-------

To install E3, you'll need a 2.7.x version of Python.

```bash
python setup.py install
```

All E3 dependencies will also be installed.

Contributing
------------

See [CONTRIBUTING.md](CONTRIBUTING.md).