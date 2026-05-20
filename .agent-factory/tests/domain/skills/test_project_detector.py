"""Project skill detector placement coverage."""

from __future__ import annotations

from pathlib import Path


def test_project_detector_imports_from_core_skills_boundary() -> None:
    from engine.core.skills import project_detector

    assert project_detector._detect_node_stack("/definitely/missing") == ["Node.js"]


def test_flow_detect_wrapper_points_to_core_skills() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    wrapper = repo_root / ".agent-factory" / "bin" / "flow-detect"

    assert "engine/core/skills/project_detector.py" in wrapper.read_text(encoding="utf-8")
