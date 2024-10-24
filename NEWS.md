# Version 22.7.0 (2024-??-??) *NOT RELEASED YET*
* Fix SPDX document version
* Take `main.Main` name's argument as the arguments parser's prog name
* Add DLL closure check to Anod class
* Add git_shallow_fetch_since to checkout.py
* Accept `pathlib.Path` in `e3.fs`, `e3.os.fs`, and `e3.os.process`

* Backward incompatible change:
  * Remove e3.config and typeguard dependency. This removes the possibility
    to configure the default e3.log formatting using `e3.toml`

# Version 22.6.0 (2024-06-19)

* Fix encoding/vex action statement for affected products
* Add ability to pass parameters to a plan entry point on execution
* Fix e3-pypi-closure name comparison
* Add 'comment' file to list of file to ignore
* Handle `pycoverage` backward incompatibility of the `CoverageData.update()`
  method.
* Add types-mock as check dependency
* Fix pytest when source coverage is not used
* deps: exchange ld for distro
* Add .gitlab-ci.yaml to VCS_IGNORE_LIST
* Silence "cannot parse version" warning by default
* e3.sys: Replace pkg_resources by importlib.metadata

# Version 22.5.0 (2024-04-07)

* Add e3.pytest plugin to reuse fixtures in other projects
* Add support for VEX documents
* Update e3-pypi-closure to generate more precise version
* Enable Anod class to use methods instead of properties
* Ensure e3 is handled as a PEP 420 namespace
* Add secure_control_plane to anod

# Version 22.4.0 (2024-01-18)

* Security enhancements:
  * e3.net.smtp.sendmail uses to ``SMTP_SSL`` by default

* New Anod API Version 1.6:
  * For performance issues declare dynamically "spec" function in the
    Anod spec context rather than using e3.anod.loader.spec function
    that relies on inspect module

# Version 22.3.1 (2023-03-17)

* Add rlimit binary for aarch64-darwin

# Version 22.3.0 (2023-03-09)

* Add support for M1/M2 MacOS (aarch64-darwin platform)
* e3.diff.patch raise an exception if there is no file to patch
* Fix issue where anod download deps are not tracked
* Add a SPDX document generator
* Add an interface to NVD API

# Version 22.2.0 (2022-08-31)

* Minor backward incompatible changes:
  * the discrimiant ``is_virtual`` has been removed
  * e3.anod.sandbox.SandBox now has a mandatory root_dir attribute
  * AnodSpecRepositories spec_config should now subclass SpecConfig
  * PlanContext now returns PlanActionEnv, a subclass of BaseEnv. Contrary
    to the previous BaseEnv objects, returned PlanActionEnv always have
    the following attributes set: "push_to_store", "default_build",
    "module", "source_packages"

# Version 22.1.0 (2020-06-22)

* Add type hinting and verify it with ``mypy``
* Minor backward incompatible changes:
  * some function argument are now mandatory:
    * e3.anod.context.AnodContext.add_anod_action ``env``
    * e3.anod.context.AnodContext.add_spec ``env`` and ``primitive``
  * some attribute have been replaced by properties to avoid being marked as Optional
    * e3.anod.spec.Anod ``build_space``
  * e3.os.process out and err attributes preserve CR characters
* Deprecate e3.decorator.memoize, use functools.lru_cache instead
* Prevent crash when a process launched by e3.os.process.Run does not emit utf-8
  on stdout or stderr. Output and error is now processed using bytes_as_str and
  bytes version of output and error is available through raw_out and raw_err
  attributes.

# Version 22.0.0 (2020-03-13)

Convert code to support Python >= 3.7 only.

# Version 21.0.0 (2020-01-13)

This is the last version supporting Python 2. Next major version will be Python 3 only.

## Backward incompatible changes since 20.08

### e3.event

* e3.event has been modified in order to support multiple event
  handlers at the same time

### e3.os

* On Windows e3.os.process.Run always create process group

### e3.anod

* Reject explicits calls to install() when build() is needed
* Reject duplicated actions in plan


## Enhancements

### General

* Add support for 64bit windows

### e3.collection

* Many performance enhancements to e3.collection.dag

### e3.electrolyt

* Improve plan error messages
* Greatly improve e3-plan-checker performance
* Linke DAG actions to plan lines

### e3.fs

* New function directory_content
* Allow passing generator to e3.fs.ls

### e3.net

* Add support for JSON Web Token (JWT)
* Allow SSL connection to SMTP servers

### e3.os

* Ensure we can detect windows server versions higher than 2012

# Version 20.08 (2016-06-17)

Initial version
