# Version 22.1.0 (2020-??-??) *NOT RELEASED YET*

* Add type hinting and verify it with ``mypy``
* Minor backward incompatible changes:
  * some function argument are now mandatory:
    * e3.anod.context.AnodContext.add_anod_action ``env``
    * e3.anod.context.AnodContext.add_spec ``env`` and ``primitive``
  * some attribute have been replaced by properties to avoid being marked as Optional
    * e3.anod.spec.Anod ``build_space``

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
