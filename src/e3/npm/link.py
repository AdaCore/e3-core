from __future__ import annotations

from datetime import datetime, timezone
from dateutil.parser import parse as dateutil_parse
from typing import TYPE_CHECKING

from e3.net.http import WeakSession

if TYPE_CHECKING:
    from requests import Session
    from requests_cache import CachedSession


class NPMLink:
    def __init__(
        self,
        name: str,
        version: str,
        url: str,
        checksum: str,
        *,
        creation_date: str | None = None,
        metadata: dict[str, object] | None = None,
        session: CachedSession | Session | None = None,
    ) -> None:
        """NPM download link metadata.

        :param name: The package name
        :param version: The package version
        :param url: The download url
        :param checksum: The sha1 checksum of the package
        :param creation_date: The package creation date, or None if not provided.
        :param metadata: The NPM metadata for this package.
            This field contains the metadata as returned by
            https://registry.npmjs.org/<YOUR PACKAGE>/<YOUR PACKAGE VERSION>.
        :param session: An optional user session to use. If provided, the user is
            responsible for the session lifetime. If None, it will use the return value
            of :py:meth:`WeakSession.default`.
        """
        self.session = WeakSession(session)

        tmp = name.rsplit("/", 1)
        if len(tmp) == 2:
            pkg_scope, pkg_name = tmp
        else:
            pkg_name = tmp[0]
            pkg_scope = ""

        self.name = name
        self.filename = f"{pkg_name}-{version}.tgz"
        self.package_name = pkg_name
        self.package_scope = pkg_scope
        self.version = version
        self.url = url
        self.checksum = checksum
        self.metadata = metadata
        self.creation_date: datetime | None = (
            dateutil_parse(creation_date) if creation_date else None
        )

    @property
    def last_modified(self) -> datetime | None:
        """Retrieve the Last-Modified HTTP header.

        This header can be used if the creation date of a package is not provided
        by the package metadata.

        If this property is called multiple times, it's strongly encouraged to use a
        CachedSession to avoid unecessary HTTP requests. If no user session is provided
        a CachedSession is used by default.

        :return: The datetime representation of the Last-Modified HTTP header, or None
            if not provided.
        """
        with self.session as session:
            data = session.head(self.url)
            data.raise_for_status()
            last_modified_str = data.headers.get("Last-Modified")

        if not last_modified_str:
            return None

        return datetime.strptime(last_modified_str, "%a, %d %b %Y %H:%M:%S %Z").replace(
            tzinfo=timezone.utc
        )
