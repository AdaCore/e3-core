"""Tests for e3.electrolyt.host."""

from pathlib import Path

import e3.electrolyt.host as host


def test_host_db() -> None:
    """Test host db."""
    db = host.HostDB()
    db.add_host(
        hostname="computer1",
        platform="x86_64-linux",
        version="rhes5",
        data_center="dc832",
    )

    assert db.hostnames == ["computer1"]
    assert db.get("computer1").data_center == "dc832", db.get("computer1").__dict__
    assert db["computer1"].platform == "x86_64-linux"


def test_host_db_yaml() -> None:
    """Test host db yaml."""
    with Path("db.yaml").open("w") as f:
        f.write(
            "computer2:\n"
            "   build_platform: x86-windows\n"
            "   build_os_version: 2008R2\n"
            "   data_center: dc993\n\n"
            "computer3:\n"
            "   build_platform: x86_64-darwin\n"
            "   build_os_version: 16.3\n"
            "   data_center: dcmac\n"
        )

    db = host.HostDB(filename="db.yaml")
    assert set(db.hostnames) == {"computer2", "computer3"}
    assert db["computer3"].platform == "x86_64-darwin"


def test_host_db_yaml_alias() -> None:
    """Test host db yaml alias."""
    with Path("db.yaml").open("w") as f:
        f.write(
            "computer2: &computer2_alias\n"
            "   build_platform: x86-windows\n"
            "   build_os_version: 2008R2\n"
            "   data_center: dc993\n\n"
            "computer3: *computer2_alias\n"
        )

    db = host.HostDB(filename="db.yaml")
    assert set(db.hostnames) == {"computer2", "computer3"}
    assert db["computer3"].platform == "x86-windows"
