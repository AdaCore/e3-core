from __future__ import annotations

import json
import requests

from e3.log import getLogger

logger = getLogger("e3.maven")


class MavenLink:
    def __init__(self, group: str, name: str, version: str) -> None:
        """Maven download link metadata.

        Note:
        -----
        Checksum is not handled here because maven provides file checksum directly
        in the HTTP request header using: x-checksum-md5 or x-checksum-sha1
        The request URL is not provided, because the code will compute it depending on
        the package group/name/version.

        :param group: The package group
        :param name: The package name
        :param version: The package version
        """
        filename = f"{name}-{version}.jar"
        self.filename = filename
        self.package_group = group
        self.package_name = name
        self.version = version
        self.url = f"https://repo1.maven.org/maven2/{group}/{name}/{version}/{filename}"


class MavenLinksParser:
    def __init__(self) -> None:
        """Create the MavenLinksParser."""
        self.links: list[MavenLink] = []

    def _raise_missing_key(self, key: str) -> None:
        raise KeyError(
            f"Maven links parser failed: key {key!r} is missing from the HTTP answer"
        )

    def feed(self, data: str) -> MavenLinksParser:
        """See HTMLParser.feed."""
        docs = json.loads(data).get("response", {}).get("docs")
        if not docs:
            self._raise_missing_key("response:docs")

        for pkgmeta in docs:
            for k in ("g", "a", "v"):
                if k not in pkgmeta:
                    self._raise_missing_key(f"response:docs:{k}")

            group = pkgmeta["g"]
            name = pkgmeta["a"]
            version = pkgmeta["v"]
            self.links.append(MavenLink(group, name, version))
        return self


class Maven:
    def __init__(self, url: str = "https://search.maven.org/solrsearch/select") -> None:
        """Initialize Maven manager class.

        :param url: The package search URL
        """
        self.url = url
        self.cache: dict[str, list[MavenLink]] = {}

    def fetch_project_links(
        self,
        group: str,
        name: str,
        *,
        headers: dict[str, str | bytes | None] | None = None,
    ) -> list[MavenLink]:
        """Fetch list of resources for a given Maven package.

        :param name: Maven package name
        :param headers: To add additionnal headers to the HTTP request. Can be mandatory
            depending on the situation.
        :return: a list of dict containing the link to each resource along with
            some metadata
        """
        if name not in self.cache:
            logger.debug(f"fetch {name} links from {self.url}")
            request = requests.get(
                f"{self.url}?q="
                f"g:%22{group}%22+AND+a:%22{name}%22&core=gav&rows=20&wt=json",
                headers=headers,
            )
            request.raise_for_status()

            # Update cache
            self.cache[name] = MavenLinksParser().feed(request.text).links
        return self.cache[name]
