from __future__ import annotations

import json
import requests

from e3.log import getLogger

logger = getLogger("e3.maven")


class MavenLink:
    def __init__(self, group: str, name: str, version: str) -> None:
        """Maven download link metadata.

        :param group: The package group.
        :param name: The package name.
        :param version: The package version.
        """
        filename = f"{name}-{version}.jar"
        self.filename = filename
        self.package_group = group
        self.package_name = name
        self.version = version
        self.url = (
            f"https://repo1.maven.org/maven2/{group.replace('.', '/')}/{name}/{version}"
            f"/{filename}"
        )

        # To get the expected checksum of the current file, we need to make an
        # additonnal HEAD request. This is because maven send the checksum directly on
        # the HTTP header.
        hdrs = requests.head(self.url).headers

        # Maven support two type of checksums
        sha1_checksum = hdrs.get("x-checksum-sha1")
        md5_checksum = hdrs.get("x-checksum-md5")
        if not md5_checksum and not sha1_checksum:
            raise RuntimeError(f"No checksum provided for {group}/{self.filename}")

        # No 'elif' because maven can send both together into HTTP headers.
        if md5_checksum:
            self.md5_checksum = md5_checksum
        if sha1_checksum:
            self.sha1_checksum = sha1_checksum


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
            # First get the number of elements to retrieve using rows=0.
            # This will return a JSON like:
            # {
            #   "reponseHeader": { ... },
            #   "reponse" : {
            #       "numFound": X,
            #       ...
            #   }
            # }
            #
            # The numFound is the number of rows to ask. Currently, we don't find any
            # case where this number is too big for making only one query.
            tmp_request = requests.get(
                f"{self.url}?q="
                f"g:%22{group}%22+AND+a:%22{name}%22&core=gav&rows=0&wt=json",
                headers=headers,
            )
            tmp_request.raise_for_status()

            tmp = tmp_request.json()

            if "response" not in tmp or "numFound" not in tmp["response"]:
                raise KeyError(
                    "Cannot determine the number of rows to request: "
                    "'response:numFound' key not found."
                )

            rows = tmp["response"]["numFound"]

            # Now, we have our numbers of rows, so lets make the same request, but with
            # the right parameters.
            request = requests.get(
                f"{self.url}?q="
                f"g:%22{group}%22+AND+a:%22{name}%22&core=gav&rows={rows}&wt=json",
                headers=headers,
            )
            request.raise_for_status()

            # Update cache
            self.cache[name] = MavenLinksParser().feed(request.text).links
        return self.cache[name]
