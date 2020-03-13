# Check that spec_config is in globals is need just because of
# style checking. This is not required in practic
if "spec_config" not in globals():
    spec_config = None

if spec_config is not None:
    PROLOG_WAS_EXECUTED = True
