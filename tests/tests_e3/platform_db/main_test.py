import pkg_resources
import stevedore
from e3.platform_db import get_knowledge_base


def test_knownledge_base():
    """Test loading a e3.platform_db extension."""
    # Create a new entry point referencing AmberCPUSupport and load it.
    mydb_ep = pkg_resources.EntryPoint.parse_group(
        "e3.platform_db",
        ["mydb = e3.platform_db:AmberCPUSupport"],
        dist=pkg_resources.get_distribution("e3-core"),
    )["mydb"]
    mydb_ep.load()

    # Inject it in the ExtensionManager entry point cache

    old_cache = stevedore.ExtensionManager.ENTRY_POINT_CACHE
    try:
        stevedore.ExtensionManager.ENTRY_POINT_CACHE["e3.platform_db"].append(mydb_ep)

        # Force a reload of the platform_db knowledge base
        db = get_knowledge_base(reset_cache=True)

        # Check that the new amber CPU has been inserted
        for cpu_name in ("amber23", "amber25"):
            assert db.cpu_info[cpu_name] == {"endian": "little", "bits": 32}
    finally:
        # restore entry point cache
        stevedore.ExtensionManager.ENTRY_POINT_CACHE = old_cache
