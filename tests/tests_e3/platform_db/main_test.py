import stevedore
from e3.platform_db import get_knowledge_base
from importlib.metadata import EntryPoint


def test_knownledge_base():
    """Test loading a e3.platform_db extension."""
    # Create a new entry point referencing AmberCPUSupport and load it.
    mydb_ep = EntryPoint(
        name="mydb", value="e3.platform_db:AmberCPUSupport", group="e3.platform_db"
    )
    mydb_ep.load()

    # Inject it in the ExtensionManager entry point cache

    old_cache = stevedore.ExtensionManager.ENTRY_POINT_CACHE
    try:
        stevedore.ExtensionManager.ENTRY_POINT_CACHE["e3.platform_db"].append(mydb_ep)

        db = get_knowledge_base()
        # Check that the new amber CPU has been inserted
        for cpu_name in ("amber23", "amber25"):
            assert cpu_name not in db.cpu_info

        # Force a reload of the platform_db knowledge base
        get_knowledge_base.cache_clear()
        db = get_knowledge_base()

        # Check that the new amber CPU has been inserted
        for cpu_name in ("amber23", "amber25"):
            assert db.cpu_info[cpu_name] == {"endian": "little", "bits": 32}
    finally:
        # restore entry point cache
        stevedore.ExtensionManager.ENTRY_POINT_CACHE = old_cache
