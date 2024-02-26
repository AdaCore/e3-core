from __future__ import annotations

from functools import cached_property
from requests import Session

from e3.log import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterator

logger = getLogger("cve")


class CVE:
    """Represent a CVE entry."""

    def __init__(self, json_content: dict[str, Any]) -> None:
        """Initialize a CVE instance.

        :param json_content: dict coming from NVD cves API
        """
        self.json_content = json_content

    @cached_property
    def cve_id(self) -> str:
        """Return the CVE ID."""
        return self.json_content["id"]

    @property
    def nvd_url(self) -> str:
        """Return the nvd.nist.gov vulnerability URL for that CVE."""
        return f"https://nvd.nist.gov/vuln/detail/{self.cve_id}"


class NVD:
    """Provide access to the NVD API."""

    def __init__(
        self,
        cache_db_path: str | None = None,
        cache_backend: str | None = None,
        nvd_api_key: str | None = None,
    ) -> None:
        """Initialize a NVD instance.

        :param cache_db_path: path to the cache database [strongly recommended]
            if the path is valid but the file does not exist, the database will
            be created when searching for CVE. Note that this requires requests-cache
            package.
        :param cache_backend: which requests_cache backend to use, default is
            sqlite
        :param nvd_api_key: the API key to use to avoid drastic rate limits
        """
        self.cache_db_path = cache_db_path
        if self.cache_db_path is None:
            logger.warning(
                "the use of a cache for NVD requests is strongly recommended"
            )
        self.cache_backend = cache_backend
        self.nvd_api_key = nvd_api_key
        if self.nvd_api_key is None:
            logger.warning(
                "the use of an API key for the NVD API is strongly recommended"
                " to avoid rate limits"
            )
        self._session: Session | None = None

    def search_by_cpe_name(
        self,
        cpe_name: str,
        is_vulnerable: bool = True,
        no_rejected: bool = True,
        results_per_page: int | None = None,
    ) -> Iterator[CVE]:
        """Return a list of matching CVE entries.

        :param no_rejected: remove CVE records with the REJECT or Rejected
            status from API response
        :param results_per_page: number of results to return for each request,
             note that it is recommended to keep the default setting
        """
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cpeName={cpe_name}"
        if is_vulnerable:
            url += "&isVulnerable"
        if no_rejected:
            url += "&noRejected"
        if results_per_page:
            url += f"&resultsPerPage={results_per_page}"

        if self.nvd_api_key is not None:
            headers: dict[str, str] | None = {"apiKey": self.nvd_api_key}
        else:
            headers = None

        start_index = 0
        while True:
            r = self.session.get(url + f"&startIndex={start_index}", headers=headers)
            r_json = r.json()
            vulnerabilities = r_json["vulnerabilities"]
            total_results = r_json["totalResults"]
            if not total_results:
                break
            # We should always have something to read if there are some results
            assert r_json["resultsPerPage"] != 0
            for cve_entry in vulnerabilities:
                yield CVE(cve_entry["cve"])
            if (total_results - start_index) > r_json["resultsPerPage"]:
                # Some results are missing
                start_index += r_json["resultsPerPage"]
            else:
                break

    def __enter__(self) -> Any:
        """Return an http requests Session supporting cache.

        Use requests_cache CachedSession when cache is requested.
        """
        if self._session is not None:
            return self

        if self.cache_db_path:
            from requests_cache import CachedSession
            from datetime import timedelta

            self._session = CachedSession(
                self.cache_db_path,
                backend=self.cache_backend,
                # Use Cache-Control headers for expiration, if available
                cache_control=True,
                # Otherwise renew the cache every day
                expire_after=timedelta(days=1),
                # Use cache data in case of errors
                stale_if_error=True,
                # Ignore headers
                match_header=False,
            )
            logger.debug(f"using requests cache from {self.cache_db_path}")
        else:
            self._session = Session()
        return self

    def __exit__(self, _type: Any, _value: Any, _tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    @property
    def session(self) -> Session:
        if self._session is None:
            from warnings import warn

            warn(
                "Using NVD.session without using `with` statement is deprecated",
                DeprecationWarning,
            )
            self.__enter__()

        return self._session  # type: ignore[return-value]
