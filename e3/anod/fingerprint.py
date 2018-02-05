"""Fingerprints handling.

Fingerprints objects are used by Anod to keep track of build, install states
and allow Anod to detect changes in these states. This is mainly used to
decide if a given action has been done and is up-to-date.
"""

from __future__ import absolute_import, division, print_function

import hashlib
import os

from e3.anod.error import AnodError
from e3.env import Env
from e3.hash import sha1

FINGERPRINT_VERSION = '1.1'
# This value should be bumped each time computation of the fingerprint changes.
# This ensures we don't try to compare fingerprints with different meanings.


class Fingerprint(object):
    """Fingerprint class.

    :ivar elements: a dictionary containing the checksum/id for each element
        part of of the fingerprint. The key a string identifying the
        element.
    """

    def __init__(self):
        """Initialise a new fingerprint instance."""
        self.elements = {}
        self.add('os_version', Env().build.os.version)
        # ??? add more detailed information about the build machine so that
        # even a minor OS upgrade trigger a rebuild

        self.add('fingerprint_version', FINGERPRINT_VERSION)

    def add_instance(self, anod_instance):
        """Add the fingerprint of an Anod instance.

        The fingerprint is based on the following elements:

        - the .anod and associated .yaml files
        - the sources used by this instanced
        - the direct dependency fingerprints

        :param anod_instance: an Anod instance
        :type anod_instance: e3.anod.spec.Anod
        """
        # ??? add all anod specs related files (.anod and .yaml)

        # ??? Add build variables (BuildVar)

        # ??? Do likewise for all the sources used by this anod instance

        # ??? Update fingerprint for dependencies

    def add(self, name, value):
        """Add a fingerprint element.

        :param name: name of the new element
        :type name: str
        :param value: associated value (should be a string)
        :type value: str | unicode
        :raise: AnodError
        """
        if isinstance(value, (str, unicode)):
            self.elements[name] = value
        else:
            raise AnodError(
                'value for %s should be a string got %s' % (name, value),
                'fingerprint.add')

    def add_file(self, filename):
        """Add a file element to the fingerprint.

        :param filename: a path
        :type filename: str

        Adding a filename element to a fingerprint is equivalent to do add
        an element for which key is the basename of the file and value is
        is the sha1 of the content
        """
        assert os.path.isfile(filename), \
            'filename %s does not exist' % filename
        self.elements[os.path.basename(filename)] = sha1(filename)

    def __eq__(self, other):
        """Implement == operator for two fingerprints.

        :param other: object to compare with
        :type other: Fingerprint

        :rtype: bool

        Two fingerprints are considered equals if both arguments are
        fingerprints and all elements of the fingerprint are equal
        """
        if not isinstance(other, Fingerprint):
            # The argument is not a fingerprint so return False
            return False

        if set(self.elements.keys()) != set(other.elements.keys()):
            # If the set of keys for each fingerprint is not equal
            # return False
            return False

        for k in self.elements:
            if self.elements[k] != other.elements[k]:
                return False

        return True

    def __ne__(self, other):
        """Implement != operator for two fingerprints.

        See __eq__ functions.
        :type other: Fingerprint
        """
        return not self == other

    def compare_to(self, other):
        """Compare two fingerprints and return the differences.

        :type other: Fingerprint

        :return: a dictionary that list the differences or None if the two
          Fingerprint are equals. The returned dictionary contains three
          items. 'updated' list the elements that are in both fingerprints but
          that are different, 'obsolete' list the elements that are only in
          self, and 'new' the elements that are only in other
        :rtype: None | dict[str][str]

        :raise AssertError: if other is not a Fingerprint
        """
        assert isinstance(other, Fingerprint), \
            'can compare only with Fingerprint objects'

        self_key_set = set(self.elements.keys())
        other_key_set = set(other.elements.keys())

        obsolete = self_key_set - other_key_set
        new = other_key_set - self_key_set

        # Compare common elements
        updated = set()
        for k in self_key_set & other_key_set:
            if self.elements[k] != other.elements[k]:
                updated.add(k)

        if len(updated) == 0 and len(new) == 0 and len(obsolete) == 0:
            return None
        else:
            return {'updated': updated,
                    'new': new,
                    'obsolete': obsolete}

    def __str__(self):
        """Return a string representation of the fingerprint.

        :rtype: str
        """
        return '\n'.join(['%s: %s' % (k, self.elements[k])
                          for k in sorted(self.elements.keys())])

    def sha1(self):
        """Get fingerprint checksum.

        :rtype: str

        The function ensure that if two fingerprints are equals then
        the returned checksum for each of the fingerprint is equal.
        """
        key_list = self.elements.keys()
        key_list.sort()
        checksum = hashlib.sha1()
        for key in key_list:
            for chunk in (key, self.elements[key]):
                if isinstance(chunk, unicode):
                    checksum.update(chunk.encode('utf-8'))
                else:
                    checksum.update(chunk)
        return checksum.hexdigest()
