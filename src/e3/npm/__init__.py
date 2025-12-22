from __future__ import annotations

from requests import Session
from typing import TYPE_CHECKING

from .link import NPMLink
from .parser import NPMLinksParser

from e3.log import getLogger

if TYPE_CHECKING:
    from requests_cache import CachedSession

logger = getLogger("npm")


class NPM:
    def __init__(self, url: str = "https://registry.npmjs.org/") -> None:
        """Initialize NPM manager class.

        :param url: The package search URL.
        """
        self.url = url if url.endswith("/") else f"{url}/"
        self.cache: dict[str, list[NPMLink]] = {}

    def fetch_project_links(
        self,
        name: str,
        *,
        headers: dict[str, str | bytes | None] | None = None,
        session: CachedSession | Session | None = None,
    ) -> list[NPMLink]:
        """Fetch list of resources for a given NPM package.

        :param name: NPM package name
        :param headers: To add additionnal headers to the HTTP request. Can be mandatory
            depending on the situation.
        :param session: An optional user session to use. If None, a requests.Session is
            used.
        :return: a list of dict containing the link to each resource along with
            some metadata
        """
        session = session or Session()
        if name not in self.cache:
            logger.debug(f"fetch {name} links from {self.url}")
            request = session.get(f"{self.url}{name}", headers=headers)
            request.raise_for_status()
            # Update cache
            self.cache[name] = NPMLinksParser().feed(request.text).links
        return self.cache[name]
