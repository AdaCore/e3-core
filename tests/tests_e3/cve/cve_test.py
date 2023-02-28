from e3.cve import NVD

import os


def test_nvd_cve_search(socket_disabled):
    """Test the CVE DB research using cached data."""
    cache_db = os.path.join(os.path.dirname(__file__), "cache.db")

    nvd_db = NVD(cache_db_path=cache_db)
    cve_urls = [
        cve.nvd_url
        for cve in nvd_db.search_by_cpe_name(
            "cpe:2.3:a:libpng:libpng:1.6.0:-:*:*:*:*:*:*", results_per_page=5
        )
    ]
    assert cve_urls == [
        "https://nvd.nist.gov/vuln/detail/CVE-2013-6954",
        "https://nvd.nist.gov/vuln/detail/CVE-2014-0333",
        "https://nvd.nist.gov/vuln/detail/CVE-2014-9495",
        "https://nvd.nist.gov/vuln/detail/CVE-2015-0973",
        "https://nvd.nist.gov/vuln/detail/CVE-2015-8126",
        "https://nvd.nist.gov/vuln/detail/CVE-2015-8472",
        "https://nvd.nist.gov/vuln/detail/CVE-2016-3751",
        "https://nvd.nist.gov/vuln/detail/CVE-2016-10087",
        "https://nvd.nist.gov/vuln/detail/CVE-2019-7317",
        "https://nvd.nist.gov/vuln/detail/CVE-2017-12652",
        "https://nvd.nist.gov/vuln/detail/CVE-2021-4214",
    ]
