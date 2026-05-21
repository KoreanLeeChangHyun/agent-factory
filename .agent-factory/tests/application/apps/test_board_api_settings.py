"""Tests for Settings board API app boundary."""

from __future__ import annotations

from board.server.handlers.settings import SettingsHandlerMixin as CompatSettingsHandlerMixin
from board.factory_sources import settings as settings_source
from engine.apps.board_api.settings import SettingsHandlerMixin


def test_settings_handler_compat_export_matches_app_boundary() -> None:
    assert CompatSettingsHandlerMixin is SettingsHandlerMixin


def test_settings_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(SettingsHandlerMixin, "_handle_settings_workflow_sync")


def test_parse_env_file_uses_project_git_config_for_optional_identity_override(tmp_path, monkeypatch) -> None:
    settings_dir = tmp_path / ".agent-factory"
    settings_dir.mkdir()
    (settings_dir / ".settings").write_text(
        "# (1) Git identity settings\n"
        "GIT_USER_NAME=\n"
        "GIT_USER_EMAIL=\n",
        encoding="utf-8",
    )

    def fake_git_config(_project_root: str, key: str) -> str:
        return {
            "user.name": "Project User",
            "user.email": "project@example.com",
        }[key]

    monkeypatch.setattr(settings_source, "_read_git_config", fake_git_config)

    sections = settings_source._parse_env_file(str(tmp_path))
    values = {item["key"]: item["value"] for item in sections[0]["vars"]}

    assert values["GIT_USER_NAME"] == "Project User"
    assert values["GIT_USER_EMAIL"] == "project@example.com"


def test_parse_env_file_does_not_require_git_identity_settings(tmp_path) -> None:
    settings_dir = tmp_path / ".agent-factory"
    settings_dir.mkdir()
    (settings_dir / ".settings").write_text(
        "# (1) Git identity settings\n"
        "GITHUB_USERNAME=\n"
        "SSH_KEY_GITHUB=\n",
        encoding="utf-8",
    )

    sections = settings_source._parse_env_file(str(tmp_path))
    keys = [item["key"] for item in sections[0]["vars"]]

    assert keys == ["GITHUB_USERNAME", "SSH_KEY_GITHUB"]
