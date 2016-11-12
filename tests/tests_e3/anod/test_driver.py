from __future__ import absolute_import, division, print_function

import os

import e3.anod.driver
import e3.anod.sandbox
import e3.anod.spec
import pytest


def test_simple_driver():
    sandbox = e3.anod.sandbox.SandBox()

    class Simple(e3.anod.spec.Anod):
        pass

    with pytest.raises(e3.anod.spec.AnodError):
        anod_instance = Simple(
            qualifier='', kind='build')
        anod_instance.sandbox = None
        e3.anod.driver.AnodDriver(
            anod_instance=anod_instance,
            store=None).activate()

    sandbox.root_dir = os.getcwd()
    anod_instance = Simple(
        qualifier='', kind='build')
    anod_instance.sandbox = sandbox
    driver = e3.anod.driver.AnodDriver(
        anod_instance=anod_instance,
        store=None)

    assert driver.call('why') is False
