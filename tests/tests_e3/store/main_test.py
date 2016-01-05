from __future__ import absolute_import

import httpretty
import httpretty.core
import tempfile

from e3.fs import rm
from e3.store.backends.http_simple_store import HTTPSimpleStore


def test_simple_store(caplog):
    with httpretty.core.httprettized():
        httpretty.HTTPretty.allow_net_connect = False

        httpretty.register_uri(
            httpretty.GET,
            'http://test.example',
            body='a body content',
            content_disposition='attachment; filename="foo.tar.gz"')
        query = {'url': 'http://test.example',
                 'sha': 'da39a3ee5e6b4b0d3255bfef95601890afd80709'}

        store = HTTPSimpleStore({}, None)
        metadata = store.get_resource_metadata(query)
        assert {metadata.url, metadata.sha} == set(query.values())

        tmpd = tempfile.mkdtemp()
        try:
            path = store.download_resource_content(metadata, tmpd)
            assert path is None
            assert any(
                ('expecting da39a3ee5e6b4b0d3255bfef95601890afd80709 got'
                 in c.getMessage() for c in caplog.records()))

            metadata.sha = '0c8ef1a401f4564abba7b85676464ac4bbb5cb05'
            path = store.download_resource_content(metadata, tmpd)
            assert path is not None
        finally:
            rm(tmpd, True)
