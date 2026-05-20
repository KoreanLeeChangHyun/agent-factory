"""Git config adapter boundary coverage."""

from __future__ import annotations


def test_git_config_compat_wrapper_uses_adapter_main() -> None:
    from engine.adapters.git.config import main as adapter_main
    from engine.git.git_config import main as compat_main

    assert compat_main is adapter_main


def test_git_config_paths_resolve_from_adapter_location() -> None:
    from engine.adapters.git import config

    assert config._CW_DIR.endswith(".agent-factory")
    assert config._ENV_FILE.endswith(".agent-factory/.settings")
