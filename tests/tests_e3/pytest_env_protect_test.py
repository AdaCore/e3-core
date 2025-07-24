import os

from e3.pytest import set_git_env_config


def test_env_protect_test_git_config() -> None:
    """Test to ensure git config is protected.

    GIT_CONFIG_COUNT can be already set by the environment, we need to protect
    the previous values.
    """
    os.environ["GIT_CONFIG_COUNT"] = "11"
    os.environ["GIT_CONFIG_KEY_10"] = "color.diff.meta"
    os.environ["GIT_CONFIG_VALUE_10"] = "42"

    set_git_env_config()

    # After env_protect runs, the git config should be reset to default values
    assert os.environ.get("GIT_CONFIG_COUNT") == "12"
    assert os.environ.get("GIT_CONFIG_KEY_10") == "color.diff.meta"
    assert os.environ.get("GIT_CONFIG_VALUE_10") == "42"

    assert os.environ.get("GIT_CONFIG_KEY_11") == "init.defaultbranch"
    assert os.environ.get("GIT_CONFIG_VALUE_11") == "default_branch"
