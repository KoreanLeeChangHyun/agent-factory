"""Skill state core placement coverage."""

from __future__ import annotations

from pathlib import Path


def test_skill_state_imports_from_core_skills_boundary() -> None:
    from engine.core.skills import state

    assert state.is_archived("demo", {"demo": "archived"})
    assert not state.is_archived("demo", {"demo": "active"})


def test_flow_skill_wrapper_points_to_core_skills() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    wrapper = repo_root / ".agent-factory" / "bin" / "flow-skill"

    assert "engine/core/skills/state.py" in wrapper.read_text(encoding="utf-8")
