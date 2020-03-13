"""Fingerprints handling.

Fingerprints objects provides a synthetic view of a set of elements.
The purpose is to allow users to build fingerprints based on that
set of elements, and then use fingerprint comparison as fast method
for determining whether the same set of elements might have changed
since the last time those elements were checked.

One possible usage for fingerprints is determine whether something
we built is still up to date, or should be rebuilt. For that,
what we would do at the end of a successful build is we create
a fingerprint using elements such as the sources we used to perform
the build, the dependencies for our build, the version of the compiler,
etc etc. Later on, when asking ourselves whether we need to re-build
or not, we would compute a new fingerprint using the same elements,
but updated to the current situation, and compare it with the one
we previously computed. If different, we should rebuild.
"""


import hashlib
import json
import os

import e3.log
from e3.env import Env
from e3.error import E3Error
from e3.fs import get_filetree_state
from e3.hash import sha256

logger = e3.log.getLogger("fingerprint")

FINGERPRINT_VERSION = "1.2"
# This value should be bumped each time computation of the fingerprint changes.
# This ensures we don't try to compare fingerprints with different meanings.


class Fingerprint(object):
    """Fingerprint class.

    :ivar elements: a dictionary containing the checksum/id for each element
        part of the fingerprint. The key a string identifying the
        element.
    """

    def __init__(self):
        """Initialise a new fingerprint instance."""
        self.elements = {}
        self.add("os_version", Env().build.os.version)
        # ??? add more detailed information about the build machine so that
        # even a minor OS upgrade trigger a rebuild

        self.add("fingerprint_version", FINGERPRINT_VERSION)

    def add(self, name, value):
        """Add a fingerprint element.

        :param name: name of the new element
        :type name: str
        :param value: associated value (should be a string)
        :type value: str | unicode
        :raise: E3Error
        """
        if isinstance(value, str):
            self.elements[name] = value
        else:
            raise E3Error(
                "value for %s should be a string got %s" % (name, value),
                "fingerprint.add",
            )

    def add_dir(self, path):
        """Add a file tree to the fingerprint.

        :param path: a path to a directory
        :type path: str
        """
        assert os.path.isdir(path), "directory %s does not exist" % path
        self.elements[os.path.basename(path)] = get_filetree_state(path)

    def add_file(self, filename):
        """Add a file element to the fingerprint.

        :param filename: a path
        :type filename: str

        Adding a filename element to a fingerprint is equivalent to do add
        an element for which key is the basename of the file and value is
        is the sha256 of the content
        """
        assert os.path.isfile(filename), "filename %s does not exist" % filename
        self.elements[os.path.basename(filename)] = sha256(filename)

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

        :type other: Fingerprint | None

        :return: a dictionary that list the differences or None if the two
          Fingerprint are equals. The returned dictionary contains three
          items. 'updated' list the elements that are in both fingerprints but
          that are different, 'obsolete' list the elements that are only in
          self, and 'new' the elements that are only in other
        :rtype: None | dict[str][str]

        :raise AssertError: if other is not a Fingerprint
        """
        # If other is None behave as if the previous fingerprint was an empty
        # fingerprint
        if other is None:
            other = Fingerprint()

        assert isinstance(
            other, Fingerprint
        ), "can compare only with Fingerprint objects"

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
            return {"updated": updated, "new": new, "obsolete": obsolete}

    def __str__(self):
        """Return a string representation of the fingerprint.

        :rtype: str
        """
        return "\n".join(
            ["%s: %s" % (k, self.elements[k]) for k in sorted(self.elements.keys())]
        )

    def checksum(self):
        """Return the fingerprint's checksum.

        :rtype: str

        At the moment, the fingerprint uses the SHA256 hashing algorithm
        to compute the checksum.

        The function ensures that if two fingerprints are equal then
        the returned checksum for each of the fingerprint is equal.
        """
        key_list = list(self.elements.keys())
        key_list.sort()
        checksum = hashlib.sha256()
        for key in key_list:
            for chunk in (key, self.elements[key]):
                if isinstance(chunk, str):
                    checksum.update(chunk.encode("utf-8"))
                else:
                    checksum.update(chunk)
        return checksum.hexdigest()

    def save_to_file(self, filename):
        """Save the fingerprint to the given file.

        :param filename: The name of the file where to save the fingerprint.
        :type filename: str
        """
        # Save the fingerprint in a format that makes it easy for us
        # to support multiple fingerprint versions.
        #
        # For instance, while we have no metadata we want to save today
        # (eg: an attribute of the object), we can easily add a new
        # 'metadata' entry as a dictionary, with each element being
        # one piece of metadata we want to save.
        data = {"fingerprint_version": FINGERPRINT_VERSION, "elements": self.elements}

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_file(cls, filename):
        """Return the fingerprint saved in the given file.

        Return None in the following situations:
            - The file does not contain a fingerprint we recognize;
            - The fingerprint has a version number we do not support.
            - If the fingerprint file does not exist

        :param filename: The name of the file where to load the fingerprint
            from.
        :type filename: str
        :rtype: Fingerprint
        """
        if not os.path.isfile(filename):
            return None

        with open(filename) as f:
            try:
                data = json.load(f)
            except ValueError as e:
                logger.error(
                    "`%s' is not a properly formatted fingerprint file (%s)",
                    filename,
                    e,
                )
                return None

        bad_contents = None
        if not isinstance(data, dict):
            bad_contents = "not a dictionary"
        elif "fingerprint_version" not in data:
            bad_contents = '"fingerprint_version" key missing'
        elif "elements" not in data:
            bad_contents = '"elements" key missing'
        if bad_contents is not None:
            logger.error("`%s' is not a fingerprint file (%s)", filename, bad_contents)
            return None

        if data["fingerprint_version"] != FINGERPRINT_VERSION:
            logger.info(
                "Unsupported fingerprint version: %s", data["fingerprint_version"]
            )
            return None

        fingerprint = Fingerprint()
        fingerprint.elements = data["elements"]

        return fingerprint
