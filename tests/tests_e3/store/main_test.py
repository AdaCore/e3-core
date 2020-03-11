import os

from e3.store.backends.http_simple_store import HTTPSimpleStore
from e3.store.cache.backends.filecache import FileCache

import httpretty
import httpretty.core


def test_simple_store(caplog):
    """Basic test of HTTPSimpleStore."""
    with httpretty.core.httprettized():
        httpretty.HTTPretty.allow_net_connect = False

        httpretty.register_uri(
            httpretty.GET,
            "http://test.example",
            body="a body content",
            content_disposition='attachment; filename="foo.tar.gz"',
        )
        query = {
            "url": "http://test.example",
            "sha": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
        }

        store = HTTPSimpleStore({}, None)
        metadata = store.get_resource_metadata(query)
        assert {metadata.url, metadata.sha} == set(query.values())

        current_dir = os.getcwd()
        path = store.download_resource_content(metadata, current_dir)
        assert path is None
        assert "expecting da39a3ee5e6b4b0d3255bfef95601890afd80709 got" in caplog.text

        metadata.sha = "0c8ef1a401f4564abba7b85676464ac4bbb5cb05"
        path = store.download_resource_content(metadata, current_dir)
        assert path is not None


def test_store_with_cache():
    """Test HTTPSimpleStore with a FileCache."""
    fc = FileCache({"cache_dir": os.path.join(os.getcwd(), "cache")})
    with httpretty.core.httprettized():
        httpretty.HTTPretty.allow_net_connect = False

        httpretty.register_uri(
            httpretty.GET,
            "http://test.example",
            body="a body content",
            content_disposition='attachment; filename="foo.tar.gz"',
        )

        query = {
            "url": "http://test.example",
            "sha": "0c8ef1a401f4564abba7b85676464ac4bbb5cb05",
        }

        store = HTTPSimpleStore({}, fc)
        metadata = store.get_resource_metadata(query)
        current_dir = os.getcwd()
        path = store.download_resource(metadata, current_dir)
        assert path is not None
        with open(path) as f:
            assert "a body content" in f.read()

        # Calling twice should return the same result (from cache)
        path2 = store.download_resource(metadata, current_dir)
        assert path == path2

        # invalidate the cache
        cached_data = store.cache_backend.get(metadata.uid)
        with open(cached_data.local_path, "a") as f:
            f.write("-invalid")
        # the cache entry will be deleted and we should have the right result
        path3 = store.download_resource(metadata, current_dir)
        assert path == path3

        # replace the cached_data entry by 0 to raise a TypeError
        store.cache_backend.set(metadata.uid, 0)
        path4 = store.download_resource(metadata, current_dir)
        assert path == path4

        # Verify that the function returns None when the resource
        # does not exist
        metadata.sha = "fff"
        assert store.download_resource(metadata, current_dir) is None
