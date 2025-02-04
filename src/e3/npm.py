from __future__ import annotations

import json
import requests

from e3.log import getLogger

logger = getLogger("e3.npm")


class NPMLink:
    def __init__(self, name: str, version: str, url: str, checksum: str) -> None:
        """NPM download link metadata.

        :param name: The package name
        :param version: The package version
        :param url: The download url
        :param checksum: The sha1 checksum of the package
        """
        self.filename = f"{name}-{version}.tgz"
        self.package_name = name
        self.version = version
        self.url = url
        self.checksum = checksum


class NPMLinksParser:
    def __init__(self) -> None:
        """Create the NPMLinksParser."""
        self.links: list[NPMLink] = []

    def _raise_missing_key(self, key: str) -> None:
        raise KeyError(
            f"NPM links parser failed: key {key!r} is missing from the HTTP answer"
        )

    def feed(self, data: str) -> NPMLinksParser:
        """Feed this parser with retrieved JSON data.

        .. seealso: :meth:`html.parser.HTMLParser.feed`
        """
        versions = json.loads(data).get("versions")
        if not versions:
            self._raise_missing_key("versions")

        for version, val in versions.items():
            for k in ("name", "dist"):
                if k not in val:
                    self._raise_missing_key(f"versions:{version}:{k}")

            dist = val["dist"]
            for k in ("tarball", "shasum"):
                if k not in dist:
                    self._raise_missing_key(f"versions:{version}:dist:{k}")

            self.links.append(
                NPMLink(
                    val["name"],
                    version,
                    dist["tarball"],
                    dist["shasum"],
                )
            )
        return self


class NPM:
    def __init__(self, url: str = "https://registry.npmjs.org/") -> None:
        """Initialize NPM manager class.

        :param url: The package search URL
        """
        self.url = url if url.endswith("/") else f"{url}/"
        self.cache: dict[str, list[NPMLink]] = {}

    def fetch_project_links(
        self, name: str, *, headers: dict[str, str | bytes | None] | None = None
    ) -> list[NPMLink]:
        """Fetch list of resources for a given NPM package.

        :param name: NPM package name
        :param headers: To add additionnal headers to the HTTP request. Can be mandatory
            depending on the situation.
        :return: a list of dict containing the link to each resource along with
            some metadata
        """
        if name not in self.cache:
            logger.debug(f"fetch {name} links from {self.url}")
            request = requests.get(f"{self.url}{name}", headers=headers)
            request.raise_for_status()
            # Update cache
            self.cache[name] = NPMLinksParser().feed(request.text).links
        return self.cache[name]
