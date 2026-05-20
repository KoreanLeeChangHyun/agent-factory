"""Filesystem settings adapter coverage."""

from __future__ import annotations

from engine.adapters.filesystem import settings


def test_env_manage_sets_and_unsets_allowed_keys(tmp_path, monkeypatch) -> None:
    agent_factory_dir = tmp_path / ".agent-factory"
    agent_factory_dir.mkdir()
    settings_file = agent_factory_dir / ".settings"
    settings_file.write_text("HOOK_OLD=1\n", encoding="utf-8")
    monkeypatch.setattr(settings, "PROJECT_ROOT", str(tmp_path))

    assert settings.env_manage("set", "HOOK_NEW", "yes") == "env -> set HOOK_NEW=yes"
    assert "HOOK_NEW=yes\n" in settings_file.read_text(encoding="utf-8")

    assert settings.env_manage("unset", "HOOK_OLD") == "env -> unset HOOK_OLD"
    assert "HOOK_OLD=" not in settings_file.read_text(encoding="utf-8")


def test_env_manage_rejects_disallowed_keys(tmp_path, monkeypatch) -> None:
    agent_factory_dir = tmp_path / ".agent-factory"
    agent_factory_dir.mkdir()
    (agent_factory_dir / ".settings").write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "PROJECT_ROOT", str(tmp_path))

    assert settings.env_manage("set", "PATH", "/tmp") == "env -> skipped (disallowed key)"
