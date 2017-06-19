from __future__ import absolute_import, division, print_function

import os

from e3.anod.error import AnodError
from e3.anod.fingerprint import Fingerprint
from e3.env import Env

import pytest


def test_fingerprint():
    f1 = Fingerprint()
    f1.add('foo', '2')

    f2 = Fingerprint()
    f2.add('foo', '4')

    f12_diff = f2.compare_to(f1)
    assert f12_diff['new'] == set([])
    assert f12_diff['updated'] == {'foo'}
    assert f12_diff['obsolete'] == set([])

    f3 = Fingerprint()
    f3.add_file(__file__)

    f23_diff = f3.compare_to(f2)
    assert f23_diff['new'] == {'foo'}
    assert f23_diff['updated'] == set([])
    assert f23_diff['obsolete'] == {os.path.basename(__file__)}

    assert f1.sha1() != f2.sha1() != f3.sha1()

    assert Env().build.os.version in str(f3)

    f4 = Fingerprint()
    f4.add_file(__file__)
    assert f4 == f3

    f5 = Fingerprint()
    with pytest.raises(AnodError) as err:
        f5.add('f4', f4)
    assert 'f4 should be a string' in str(err.value)

    f6 = Fingerprint()
    f6.add('unicode', u'6')
    assert len(f6.sha1()) == 40


def test_fingerprint_version():
    """Changing the FINGERPRINT_VERSION modify the fingerprint sha1."""
    import e3.anod.fingerprint

    f1 = Fingerprint()

    e3.anod.fingerprint.FINGERPRINT_VERSION = '0.0'
    f2 = Fingerprint()

    assert f1 != f2

    f3 = Fingerprint()

    assert f2 == f3


def test_invalid_fingerprint():
    """A fingerprint value should be hashable."""
    with pytest.raises(AnodError):
        f1 = Fingerprint()
        f1.add('invalid', {})


def test_fingerprint_eq():
    """Check fingerprint __eq__ function."""
    f1 = Fingerprint()
    f1.add('1', '1')
    assert f1 != 1

    f2 = Fingerprint()
    f2.add('1', '1')
    f2.add('2', '2')
    assert f1 != f2

    assert f1.compare_to(f1) is None
