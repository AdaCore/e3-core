from __future__ import annotations

from e3.maven import Maven


def test_maven(maven_central) -> None:
    mvn = Maven()

    maven_central.register_package(
        group="test.e3.mvn",
        name="e3mvn",
        versions={
            "6.1.17",
            "6.1.18",
            "6.1.19",
            "6.1.20",
        },
    )
    with maven_central:
        links = mvn.fetch_project_links("test.e3.mvn", "e3mvn")

    assert len(links) == 4
    assert all(
        link.version
        in {
            "6.1.17",
            "6.1.18",
            "6.1.19",
            "6.1.20",
        }
        for link in links
    )

    assert all(link.sha1_checksum and link.md5_checksum for link in links)

    for link in links:
        data = maven_central.get_package_data(
            link.package_group, link.package_name, link.version
        )
        assert link.sha1_checksum == data["sha1"]
        assert link.md5_checksum == data["md5"]

        data = maven_central.get_pom_data(
            link.package_group, link.package_name, link.version
        )
        assert link.pom_sha1_checksum == data["sha1"]
        assert link.pom_md5_checksum == data["md5"]
