"""Maven repository utilities."""

from __future__ import annotations

import hashlib

from defusedxml.ElementTree import XMLParser
from requests import Session

from e3.log import getLogger

logger = getLogger("maven")


class MavenLink:
    """Represent Maven package download link with metadata."""

    BASE_URL = "https://repo.maven.apache.org/maven2"
    _DEFAULT_SESSION = Session()

    def __init__(
        self, group: str, name: str, version: str, *, session: Session | None = None
    ) -> None:
        """Maven download link metadata.

        :param group: The package group.
        :param name: The package name.
        :param version: The package version.
        :param session: The session object to use to make HTTP requests.
        """
        filename = f"{name}-{version}.jar"
        self.session = session or self._DEFAULT_SESSION
        self.filename = filename
        self.package_group = group
        self.package_name = name
        self.name = f"{group}/{name}"
        self.version = version
        self.url = (
            f"{self.BASE_URL}/{group.replace('.', '/')}/{name}/{version}/{filename}"
        )
        self.pom_url = f"{self.url[:-4]}.pom"

        self.__pkg_checksum = False
        self.__pom_checksum = False

    def __init_pkg_checksum(self) -> None:
        """Retrieve package checksums.

        This private method is used to initialise lazily the package checksum.
        """
        if not self.__pkg_checksum:
            # To obtain the expected checksum for the current file, we need to perform
            # an additional HEAD request. This is because Maven sends the checksum
            # directly in the HTTP headers.
            hdrs = self.session.head(self.url).headers
            self.__sha1_checksum = hdrs.get("x-checksum-sha1")
            self.__md5_checksum = hdrs.get("x-checksum-md5")
            self.__pkg_checksum = True

    def __init_pom_checksum(self) -> None:
        """Retrieve POM checksums.

        This private method is used to lazily initialise the checksum of the package's
        POM file.
        """
        if not self.__pom_checksum:
            # To obtain the expected checksum for the current file, we need to perform
            # an additional HEAD request. This is because Maven sends the checksum
            # directly in the HTTP headers.
            hdrs = self.session.head(self.pom_url).headers
            self.__pom_sha1_checksum = hdrs.get("x-checksum-sha1")
            self.__pom_md5_checksum = hdrs.get("x-checksum-md5")
            self.__pom_checksum = True

    @property
    def sha1_checksum(self) -> str | None:
        """Retrieve the SHA1 checksum of a package if any.

        :return: The SHA1 checksum if possible, otherwise None.
        """
        self.__init_pkg_checksum()
        return self.__sha1_checksum

    @property
    def md5_checksum(self) -> str | None:
        """Retrieve the MD5 checksum of a package if any.

        :return: The MD5 checksum if possible, otherwise None.
        """
        self.__init_pkg_checksum()
        return self.__md5_checksum

    @property
    def pom_sha1_checksum(self) -> str | None:
        """Retrieve the SHA1 checksum of a package's POM file if any.

        :return: The SHA1 checksum if possible, otherwise None.
        """
        self.__init_pom_checksum()
        return self.__pom_sha1_checksum

    @property
    def pom_md5_checksum(self) -> str | None:
        """Retrieve the MD5 checksum of a package's POM file if any.

        :return: The MD5 checksum if possible, otherwise None.
        """
        self.__init_pom_checksum()
        return self.__pom_md5_checksum


class MavenLinksParser:
    """Parser for Maven repository metadata XML to extract package links."""

    def __init__(
        self, group: str, name: str, *, session: Session | None = None
    ) -> None:
        """Create the MavenLinksParser.

        :param group: The package group.
        :param name: The package name.
        :param session: The session object to use to make HTTP requests.
        """
        self.links: list[MavenLink] = []
        self.group = group
        self.name = name
        self.session = session

        self.__version_already_done: set[str] = set()
        self.__should_retrieve_data = False
        self.__parser = XMLParser(target=self)

    def start(self, tag: str, attrs: dict[str, str | None]) -> None:
        """See XMLParser.start.

        :param tag: XML tag name
        :param attrs: XML tag attributes

        .. note::

            The `attrs` parameter is not used by this method implementation, but is
            defined by XMLParser.start method signature.
        """
        self.__should_retrieve_data = tag in ("version", "release", "latest")

    def data(self, text: str) -> None:
        """See XMLParser.data.

        :param text: text data from XML
        """
        text = text.strip()

        if (
            not text
            or not self.__should_retrieve_data
            or text in self.__version_already_done
        ):
            return

        self.links.append(
            MavenLink(
                group=self.group, name=self.name, version=text, session=self.session
            )
        )
        self.__version_already_done.add(text)

    def feed(self, data: str) -> MavenLinksParser:
        """See HTMLParser.feed.

        This class doesn't use the HTMLParser, but this method as the exact same
        function and logic that HTMLParser.feed.

        :param data: XML data to parse
        """
        self.__parser.feed(data)
        return self


class Maven:
    """Interface to Maven repository for package discovery and download."""

    _DEFAULT_SESSION = Session()

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
        session: Session | None = None,
    ) -> list[MavenLink]:
        """Fetch list of resources for a given Maven package.

        :param group: Maven group ID
        :param name: Maven package name
        :param headers: To add additionnal headers to the HTTP request. Can be mandatory
            depending on the situation.
        :param session: The session object to use to make HTTP requests.
        :return: a list of dict containing the link to each resource along with
            some metadata
        """
        if name not in self.cache:
            session = session or self._DEFAULT_SESSION
            logger.debug(f"fetch {name} links from {self.url}")
            request = session.get(
                f"{self.url}/{group.replace('.', '/')}/{name}/maven-metadata.xml",
                headers=headers,
            )
            request.raise_for_status()

            # The maven-metadata.xml file comes with checksum: So lets check if
            # everything is fine, just in case.
            sha1_checksum = request.headers.get("x-checksum-sha1")
            md5_checksum = request.headers.get("x-checksum-md5")
            if sha1_checksum:
                content_sha1 = hashlib.sha1(
                    request.content, usedforsecurity=False
                ).hexdigest()
                if content_sha1 != sha1_checksum:
                    msg = (
                        f"'{group}/{name}' maven-metadata.xml sha1 checksum missmatch: "
                        f"expected {sha1_checksum}, got: {content_sha1}"
                    )
                    raise RuntimeError(msg)
            elif md5_checksum:
                content_md5 = hashlib.md5(
                    request.content, usedforsecurity=False
                ).hexdigest()
                if content_md5 != md5_checksum:
                    msg = (
                        f"'{group}/{name}' maven-metadata.xml md5 checksum missmatch: "
                        f"expected {md5_checksum}, got: {content_md5}"
                    )
                    raise RuntimeError(msg)
            else:
                msg = f"'{group}/{name}' maven-metadata.xml: no checksum provided"
                raise RuntimeError(msg)

            self.cache[name] = (
                MavenLinksParser(group, name, session=session).feed(request.text).links
            )
        return self.cache[name]
