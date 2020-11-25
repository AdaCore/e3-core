import os

from e3.store.cache.backends.filecache import FileCache


def test_cache():
    fc = FileCache({"cache_dir": os.path.join(os.getcwd(), "cache")})
    fc.set("a", 1)
    assert fc.get("a") == 1
    fc.set("b", 2, timeout=-2)
    assert fc.get("b", 3) == 3
    fc.clear()
    assert fc.get("a", 0) == 0

    fc.set("a", 1)
    assert fc.get("a") == 1
    assert fc.has_resource("a")
    assert "a" in fc
    fc.delete("a")
    assert fc.get("a", 0) == 0

    assert fc.set("d", "nok", {"will": ["not", "work"]}) is False
