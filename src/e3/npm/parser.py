from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .link import NPMLink

if TYPE_CHECKING:
    from typing import NoReturn


class NPMLinksParser:
    def __init__(self) -> None:
        """Create the NPMLinksParser."""
        self.links: list[NPMLink] = []

    def _raise_missing_key(self, key: str) -> NoReturn:
        """Raise a missing key error.

        :param key: The missing key.
        :raises KeyError: Always.
        """
        raise KeyError(
            f"NPM links parser failed: key {key!r} is missing from the HTTP answer"
        )

    def feed(self, data: str) -> NPMLinksParser:
        """Feed this parser with retrieved JSON data.

        .. seealso::

            :py:meth:`html.parser.HTMLParser.feed`
        """
        json_data = json.loads(data)
        versions = json_data.get("versions")
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
                    metadata=val,
                    creation_date=json_data.get("time", {}).get(version),
                )
            )
        return self
