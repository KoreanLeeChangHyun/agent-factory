"""Git config adapter boundary coverage."""

from __future__ import annotations


def test_git_config_paths_resolve_from_adapter_location() -> None:
    from engine.adapters.git import config

    assert config._CW_DIR.endswith(".agent-factory")
    assert config._ENV_FILE.endswith(".agent-factory/.settings")


def test_git_config_project_fallback_reads_current_repo_config(monkeypatch) -> None:
    from engine.adapters.git import config

    def fake_check_output(cmd, stderr=None, timeout=None):
        assert cmd[:4] == ["git", "-C", config._PROJECT_ROOT, "config"]
        assert cmd[-1] == "user.email"
        return b"project@example.com\n"

    monkeypatch.setattr(config.subprocess, "check_output", fake_check_output)

    assert config._read_project_git_config("user.email") == "project@example.com"
