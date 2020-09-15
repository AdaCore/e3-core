# Check that spec_config is in globals is need just because of
# style checking. This is not required in practic
if "spec_config" not in globals():
    spec_config = None

if spec_config is not None:
    PROLOG_WAS_EXECUTED = True  # type: ignore
    E3_CORE_REVISION = spec_config.repositories.get("e3-core", {}).get("revision")
    E3_EXTRA_REVISION = spec_config.repositories.get("e3-extra", {}).get("revision")
    FOO = getattr(spec_config, "foo", None)
