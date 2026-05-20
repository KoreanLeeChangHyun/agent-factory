"""flow-claude-edit app CLI placement coverage."""

from __future__ import annotations

from pathlib import Path


def test_claude_edit_project_paths_resolve_from_app_cli_location() -> None:
    from engine.apps.cli import claude_edit

    repo_root = Path(__file__).resolve().parents[4]

    assert Path(claude_edit.PROJECT_ROOT) == repo_root
    assert Path(claude_edit.CLAUDE_DIR) == repo_root / ".claude"
    assert Path(claude_edit.EDIT_DIR) == repo_root / ".agent-factory" / "staging"
