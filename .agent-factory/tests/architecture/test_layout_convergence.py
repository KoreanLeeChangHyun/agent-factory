"""Directory layout convergence checks."""

from __future__ import annotations

from pathlib import Path


def test_legacy_engine_git_package_has_no_tracked_sources() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / ".agent-factory" / "engine" / "git" / "git_config.py").exists()
