from __future__ import annotations

from defusedxml.ElementTree import XMLParser
import hashlib
import requests

from e3.log import getLogger

logger = getLogger("e3.maven")


class MavenLink:
    BASE_URL = "https://repo.maven.apache.org/maven2"

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
        self.name = f"{group}/{name}"
        self.version = version
        self.url = (
            f"{self.BASE_URL}/{group.replace('.', '/')}/{name}/{version}/{filename}"
        )
        self.pom_url = f"{self.url[:-4]}.pom"

        # To get the expected checksum of the current file, we need to make an
        # additonnal HEAD request. This is because maven send the checksum directly on
        # the HTTP headers.
        hdrs = requests.head(self.url).headers
        self.sha1_checksum = hdrs.get("x-checksum-sha1")
        self.md5_checksum = hdrs.get("x-checksum-md5")

        # To get the expected checksum of the POM file, we need to make an additonnal
        # HEAD request. This is because maven sends the checksum directly on the HTTP
        # headers.
        hdrs = requests.head(self.pom_url).headers
        self.pom_sha1_checksum = hdrs.get("x-checksum-sha1")
        self.pom_md5_checksum = hdrs.get("x-checksum-md5")


class MavenLinksParser:
    def __init__(self, group: str, name: str) -> None:
        """Create the MavenLinksParser.

        :param group: The package group.
        :param name: The package name.
        """
        self.links: list[MavenLink] = []
        self.group = group
        self.name = name

        self.__version_already_done: set[str] = set()
        self.__should_retrieve_data = False
        self.__parser = XMLParser(target=self)

    def start(self, tag: str, attrs: dict[str, str | None]) -> None:
        """See XMLParser.start.

        .. note::

            The `attrs` parameter is not used by this method implementation, but is
            defined by XMLParser.start method signature.
        """
        self.__should_retrieve_data = tag in ("version", "release", "latest")

    def data(self, text: str) -> None:
        """See XMLParser.data."""
        text = text.strip()

        if (
            not text
            or not self.__should_retrieve_data
            or text in self.__version_already_done
        ):
            return

        self.links.append(
            MavenLink(
                group=self.group,
                name=self.name,
                version=text,
            )
        )
        self.__version_already_done.add(text)

    def feed(self, data: str) -> MavenLinksParser:
        """See HTMLParser.feed.

        This class doesn't use the HTMLParser, but this method as the exact same
        function and logic that HTMLParser.feed.
        """
        self.__parser.feed(data)
        return self


class Maven:
    def __init__(self, url: str = MavenLink.BASE_URL) -> None:
        """Initialize Maven manager class.

        :param url: The package search URL
        """
        self.url = url if not url.endswith("/") else url[:-1]
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
                f"{self.url}/{group.replace('.', '/')}/{name}/maven-metadata.xml",
                headers=headers,
            )
            request.raise_for_status()

            # The maven-metadata.xml file comes with checksum: So lets check if
            # everything is fine, just in case.
            sha1_checksum = request.headers.get("x-checksum-sha1")
            md5_checksum = request.headers.get("x-checksum-md5")
            if sha1_checksum:
                content_sha1 = hashlib.sha1(request.content).hexdigest()
                if content_sha1 != sha1_checksum:
                    raise RuntimeError(
                        f"'{group}/{name}' maven-metadata.xml sha1 checksum missmatch: "
                        f"expected {sha1_checksum}, got: {content_sha1}"
                    )
            elif md5_checksum:
                content_md5 = hashlib.md5(request.content).hexdigest()
                if content_md5 != md5_checksum:
                    raise RuntimeError(
                        f"'{group}/{name}' maven-metadata.xml md5 checksum missmatch: "
                        f"expected {md5_checksum}, got: {content_md5}"
                    )
            else:
                raise RuntimeError(
                    f"'{group}/{name}' maven-metadata.xml: no checksum provided"
                )

            self.cache[name] = MavenLinksParser(group, name).feed(request.text).links
        return self.cache[name]
