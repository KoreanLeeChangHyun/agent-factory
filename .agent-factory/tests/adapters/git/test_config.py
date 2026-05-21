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


def test_github_cli_status_reports_authenticated_login(monkeypatch) -> None:
    from engine.adapters.git import github_cli

    monkeypatch.setattr(github_cli, "is_gh_available", lambda: True)
    monkeypatch.setattr(github_cli, "read_authenticated_login", lambda: "octocat")

    status = github_cli.auth_status()

    assert status["installed"] is True
    assert status["authenticated"] is True
    assert status["login"] == "octocat"


def test_github_cli_start_auth_reports_existing_login(monkeypatch) -> None:
    from engine.adapters.git import github_cli

    monkeypatch.setattr(github_cli, "is_gh_available", lambda: True)
    monkeypatch.setattr(github_cli, "read_authenticated_login", lambda: "octocat")

    result = github_cli.start_web_auth()

    assert result["ok"] is True
    assert result["started"] is False
    assert result["login"] == "octocat"
