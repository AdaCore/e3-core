import json
import os

from e3.env import Env
from e3.error import E3Error
from e3.fingerprint import Fingerprint

import pytest


def test_fingerprint():
    f1 = Fingerprint()
    f1.add("foo", "2")

    f2 = Fingerprint()
    f2.add("foo", "4")

    f12_diff = f2.compare_to(f1)
    assert f12_diff["new"] == set([])
    assert f12_diff["updated"] == {"foo"}
    assert f12_diff["obsolete"] == set([])

    f3 = Fingerprint()
    f3.add_file(__file__)

    f23_diff = f3.compare_to(f2)
    assert f23_diff["new"] == {"foo"}
    assert f23_diff["updated"] == set([])
    assert f23_diff["obsolete"] == {os.path.basename(__file__)}

    assert f1.checksum() != f2.checksum() != f3.checksum()

    assert Env().build.os.version in str(f3)

    f4 = Fingerprint()
    f4.add_file(__file__)
    assert f4 == f3

    f5 = Fingerprint()
    with pytest.raises(E3Error) as err:
        f5.add("f4", f4)
    assert "f4 should be a string" in str(err.value)

    f6 = Fingerprint()
    f6.add("unicode", "6")
    assert len(f6.checksum()) == 64


def test_add_order_not_important():
    def create_fingerprint(first, second, third):
        """Create a fingerprint with 3 elements added in the given order.

        The arguments, first, second, and third should be either
        1, 2, or 3 (integers), and are meant as indices to (key, value)
        pairs in the idx_to_entry_map below, indicating which part
        of the fingerprint gets added in what order.

        :rtype: Fingerprint
        """
        idx_to_entry_map = {1: ("foo", "1"), 2: ("bar", "2"), 3: ("baz", "3")}
        f = Fingerprint()
        f.add(*idx_to_entry_map[first])
        f.add(*idx_to_entry_map[second])
        f.add(*idx_to_entry_map[third])
        return f

    f_ref = create_fingerprint(1, 2, 3)

    def check_scenario(first, second, third):
        """Check scenario where adding fingerprint elements in given order.

        Create a fingerprint using create_fingerprint above
        (same arguments), and then check the resulting key against
        the reference key f_ref above.  Both the reference fingerprint
        and the new fingerprint have the same contents, so they should
        behave the same in all ways.
        """
        f = create_fingerprint(first, second, third)
        assert f == f_ref
        assert f.compare_to(f_ref) is None
        assert f_ref.compare_to(f) is None
        assert str(f) == str(f_ref)
        assert f.checksum() == f_ref.checksum()

    check_scenario(1, 2, 3)
    check_scenario(1, 3, 2)
    check_scenario(2, 1, 3)
    check_scenario(2, 3, 1)
    check_scenario(3, 1, 2)
    check_scenario(3, 2, 1)


def test_fingerprint_version():
    """Changing the FINGERPRINT_VERSION modify the fingerprint's checksum."""
    import e3.fingerprint

    f1 = Fingerprint()

    e3.fingerprint.FINGERPRINT_VERSION = "0.0"
    f2 = Fingerprint()

    assert f1 != f2
    assert f1.checksum() != f2.checksum()

    f3 = Fingerprint()

    assert f2 == f3
    assert f2.checksum() == f3.checksum()


def test_invalid_fingerprint():
    """A fingerprint value should be hashable."""
    f1 = Fingerprint()
    with pytest.raises(E3Error):
        f1.add("invalid", {})


def test_fingerprint_eq():
    """Check fingerprint __eq__ function."""
    f1 = Fingerprint()
    f1.add("1", "1")
    assert f1 != 1

    f2 = Fingerprint()
    f2.add("1", "1")
    f2.add("2", "2")
    assert f1 != f2
    assert f1.checksum() != f2.checksum()

    assert f1.compare_to(f1) is None


def test_fingerprint_save_and_load():
    # Create a directory where to store our fingerprints, allowing us
    # to use any fingerprint name without potentially colliding with
    # other files used by this testcase.
    os.mkdir("fingerprints")

    def fingerprint_path(filename):
        return os.path.join("fingerprints", filename)

    # Save and then load a minimal fingerprint...
    f_min = Fingerprint()

    f_min_filename = fingerprint_path("f_min")
    assert not os.path.exists(f_min_filename)
    f_min.save_to_file(f_min_filename)

    f_min_restored = Fingerprint.load_from_file(f_min_filename)
    assert f_min_restored == f_min
    assert str(f_min_restored) == str(f_min)
    assert f_min_restored.checksum() == f_min.checksum()

    # Save and then load a fingerprint with more data than the minimum.

    f2 = Fingerprint()
    f2.add("job1", "job1sha1")
    f2.add("job2", "sha1job2")

    f2_filename = fingerprint_path("f2")
    assert not os.path.exists(f2_filename)
    f2.save_to_file(f2_filename)

    f2_restored = Fingerprint.load_from_file(f2_filename)
    assert f2_restored == f2
    assert str(f2_restored) == str(f2)
    assert f2_restored.checksum() == f2.checksum()

    # Trying to load from a file with invalid contents (bad JSON)

    f_bad_filename = fingerprint_path("f_bad_JSON")
    with open(f_bad_filename, "w") as f:
        f.write("yello{")

    f3 = Fingerprint.load_from_file(f_bad_filename)
    assert f3 is None

    # Trying to load from a file which contains valid data, but
    # is not an dictionary, and therefore clearly not something
    # that comes from a fingerprint...

    f_not_filename = fingerprint_path("not_a_fingerprint")
    with open(f_not_filename, "w") as f:
        json.dump([1, 2, 3], f)

    f4 = Fingerprint.load_from_file(f_not_filename)
    assert f4 is None

    # Try to load from a file which is missing one of the mandatory
    # elements.

    for key in ("fingerprint_version", "elements"):
        f_key_missing_filename = fingerprint_path("no_%s_key")

        # To create the bad file without assuming too much in this test
        # how the fingerprint is saved to file, we save a valid fingerprint
        # to file, load that file back, remove the key, and then save the
        # truncated data again.

        f2.save_to_file(f_key_missing_filename)
        with open(f_key_missing_filename) as f:
            data = json.load(f)
        del data[key]
        with open(f_key_missing_filename, "w") as f:
            json.dump(data, f)

        f5 = Fingerprint.load_from_file(f_key_missing_filename)
        assert f5 is None

    # Try loading a fingerprint whose version number is not recognized
    # (typically, and old fingerprint version that we no longer support).
    #
    # To create the file without assuming too much in this test how
    # fingerprint are saved to file, we start with a valid fingerprint
    # that we saved to a file, load that file back, adjust the version
    # number, and then replace the good fingeprint in that file by
    # the modified one.

    f_bad_version = fingerprint_path("bad_version")

    f2.save_to_file(f_bad_version)
    with open(f_bad_version) as f:
        data = json.load(f)
        data["fingerprint_version"] = "1.0"
        data["elements"]["fingerprint_version"] = "1.0"
    with open(f_bad_version, "w") as f:
        json.dump(data, f)

    f = Fingerprint.load_from_file(f_bad_version)
    assert f is None
