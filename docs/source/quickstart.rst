e3-core API highlights
======================

*e3-core* comes with many useful modules, you might find the above
selection useful to start using the *e3-core* API.

e3.fs and e3.os.fs
------------------

:py:mod:`e3.fs` and :py:mod:`e3.os.fs` modules contain several helpers
for writing portable and robust applications.

For instance :py:func:`rm` tries very hard to remove files or directories.
On Windows system it is using the :py:class:`e3.os.windows.fs.NTFile` class
that relies on ``ctypes`` to call the Windows native API. This made the removal
of files much more reliable on Windows. Using it is as simple as:

.. code-block:: python

    rm('/path/to/file')
    rm('/path/to/directory', recurive=True)
    rm('\*.py')


:py:mod:`e3.fs` also comes with many other useful functions such as :py:func:`e3.fs.sync_tree` which implement a local :program:`rsync`, with a very similar API.

Both modules implement many functions that tries to mimic the well known POSIX
tools and that are heavily tested on UNIX like platforms and Windows.

e3.os.process
-------------

In :py:mod:`e3.os.process` the :py:class:`e3.os.process.Run` class allows
running processes under a time limit.

Running:

.. code-block:: python

    Run(['python'], output=2)

will exit the :program:`python` program after 2 seconds whereas

.. code-block:: python

    Run(['python'])

will never end.

:py:class:`e3.os.process.Run` can also be used to pipe several commands, e.g.

.. code-block:: python

    p = Run([['tar', 'cf', '-', 'a_dir'], ['gzip', '-9']],
            output='a_dir.tgz',
            error=my_error_log_stream)
    assert p.status == 0


e3.main and e3.env
------------------

:py:class:`e3.main.Main` simply the writing of command line clients depending
on ``--build``, ``--host``, ``--target`` arguments. It uses
:py:class:`e3.env.Env` to set the platform environment, which is very useful if
your the tool you are writing supports multiple platforms and cross platform
environment.


Adding the following code in :program:`show-platform`

.. code-block:: python

    from e3.main import Main
    from e3.env import Env
    m = Main(platform_args=True)
    m.argument_parser.add_argument(
       '--show-platform')
    m.parse_args()
    print(Env().platform)

will print the following on a macos machine:

.. code-block:: shell

    $ show-platform
    x86_64-darwin

    $ show-platform --target=x86-windows --host=x86_64-linux
    x86-windows-linux64


Add ``print(Env().build`` will output more info on the build platform:

.. code-block:: yaml

    platform: x86_64-darwin
    machine:  ida
    is_hie:   False
    is_host:  True
    triplet:  x86_64-apple-darwin16.5.0
    domain:   unknown
    OS
       name:          darwin
       version:       16.5.0
       exeext:
       dllext:        .dylib
       is_bareboard:  False
    CPU
       name:   x86_64
       bits:   64
       endian: little
       cores:  4show-platform


e3.yaml
-------

:py:mod:`e3.yaml` comes with a *YAML* loader that loads mappings into
ordered dictionaries and with *case parser* adding case statement in
configuration files.

A case parser can be help when you want to pick different packages
depending on the build platform.

If we start with a file :file:`packages.yaml`:

.. code-block:: yaml

    packages:
        - args-0.1.0-py2-none-any.whl
        - enum34-1.1.6-py2-none-any.whl

    case_build_os_name:
        linux:
            +packages:
                - psutil-4.3.1.tar.gz
                - netifaces-0.10.4.tar.gz
        windows:
            +packages:
                - psutil-4.3.1-cp27-none-win32.whl
                - netifaces-0.10.4-cp27-none-win32.whl

Also note the special syntax ``+packages`` that adds the
new entries to the existing ``packages`` list.

The function :py:func:`e3.yaml.load_with_config` combines both:

.. code-block:: python

    e3.yaml.load_with_config('y.yaml', {'build_os_name': 'x86-windows'})

returns

.. code-block:: python

    {'packages': [
        'args-0.1.0-py2-none-any.whl',
        'enum34-1.1.6-py2-none-any.whl',
        'psutil-4.3.1-cp27-none-win32.whl',
        'netifaces-0.10.4-cp27-none-win32.whl']}
