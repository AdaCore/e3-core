from __future__ import annotations

from dateutil.parser import parse as dateutil_parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


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
        """
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
