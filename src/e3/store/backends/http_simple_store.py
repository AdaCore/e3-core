from __future__ import annotations

from typing import TYPE_CHECKING
import e3.hash
import e3.log
from e3.net.http import HTTPSession
from e3.store.backends.base import ResourceInfo, Store, StoreError

if TYPE_CHECKING:
    from typing import Dict, Optional

logger = e3.log.getLogger("store.httpsimplestore")


class HTTPSimpleStoreResourceInfo(ResourceInfo):
    def __init__(self, url: str, sha: str):
        self.url = url
        self.sha = sha

    def verify(self, resource_path: str) -> bool:
        resource_sha = e3.hash.sha1(resource_path)
        if resource_sha != self.sha:
            logger.critical(
                "wrong sha for resource %s expecting %s got %s",
                resource_path,
                self.sha,
                resource_sha,
            )
            return False
        else:
            return True

    @property
    def uid(self) -> str:
        return self.sha


class HTTPSimpleStore(Store):
    def get_resource_metadata(
        self, query: Dict[str, str]
    ) -> HTTPSimpleStoreResourceInfo:
        """Return resource metadata directly computed from the query.

        There is no remote server involved here.

        :param query: a dict containing two keys 'sha' and 'url'. sha is the
            sha1sum of the resource and url is the remote url
        """
        if "sha" not in query or "url" not in query:
            raise StoreError('missing either "sha" or "url" in query')
        return HTTPSimpleStoreResourceInfo(query["url"], query["sha"])

    def download_resource_content(
        self, metadata: ResourceInfo, dest: str
    ) -> Optional[str]:
        """Download a resource.

        :param metadata: metadata associated with the resource to download
        :param dest: where to download the resource
        :return: the path to the downloaded resource
        """
        if TYPE_CHECKING:
            assert isinstance(metadata, HTTPSimpleStoreResourceInfo)
        with HTTPSession() as http:
            return http.download_file(metadata.url, dest, validate=metadata.verify)
