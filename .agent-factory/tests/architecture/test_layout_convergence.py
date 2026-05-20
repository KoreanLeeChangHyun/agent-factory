"""Directory layout convergence checks."""

from __future__ import annotations

from pathlib import Path


def test_legacy_engine_git_package_has_no_tracked_sources() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / ".agent-factory" / "engine" / "git" / "git_config.py").exists()


def test_legacy_hook_handlers_package_has_no_tracked_sources() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    legacy_dir = repo_root / ".agent-factory" / "engine" / "hook-handlers"
    assert not (legacy_dir / "ensure_bin_path.sh").exists()
    assert not (legacy_dir / "inject_kanban_context.py").exists()


def test_legacy_engine_data_colors_symlink_is_removed() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / ".agent-factory" / "engine" / "data" / "colors.sh").exists()


def test_legacy_engine_claude_edit_source_is_removed() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / ".agent-factory" / "engine" / "claude_edit.py").exists()


def test_legacy_engine_statusline_source_is_removed() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / ".agent-factory" / "engine" / "statusline.py").exists()


def test_legacy_engine_slack_sources_are_removed() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    legacy_dir = repo_root / ".agent-factory" / "engine" / "slack"
    assert not (legacy_dir / "slack_ask.py").exists()
    assert not (legacy_dir / "slack_notify.py").exists()
    assert not (legacy_dir / "slack_common.py").exists()
