Using decision graphs for scheduling builds and tests
=====================================================

Decision graph (DG)
-------------------

Decision graphs inputs can be either a setup of user queries requesting

- builds or installs of tools or libraries
- testsuite results
- source creation
- ...

or a set of anod specification files.

The result is represented in a DAG (Directed Acyclic Graph) of *potential*
actions to be taken.

Having a DG containing all possible paths is useful for:

- conflicts detection
- implementing different decision policies through resolvers
- implementing static checks

Action graph (AG)
-----------------

This is the set of actions that should be performed represented in a DAG. Its inputs are:

- a decision graph (DG)
- a decision resolver

The decision resolver is called for each decision node in the DG for which the
ecision is either undecided, source of conflicts, or non explicit.

Using the AG (or even the DG) you can easily list resources, e.g. the list of
packages that will be pushed to (or pulled from) the store and the VCS repositories required for completing the user request.

It also becomes easy to separate online and offline local operations, allowing for instance replaying push to store and notifications without having to execute the local operation twice.

Having such graphs gives better control on the system, e.g. to plug different
store or notification systems, to upload packages to the store in parallel, ...

electrolyt plans
----------------

The electrolyt plans are written in a very small Python based DSL that is
transformed into a list of queries that are feeding the DG. It is independent
from scheduling engine and DG/DA API.

For instance the following plan:

.. code-block:: python

    anod_build('specA', qualifier='debug=true')
    with defaults(build='x86_64-windows'):
        anod_build('specB', qualifier='mode=production')

is transformed into a list of ``e3.env.BaseEnv`` objects that can be then used to build a DG.
