"""Tests for the core plan.json loader.

target: `engine.core.planning.loader` module `parse plan json` (JSON SSOT parser).

WR-504 Canon SSOT (driver = JSON / LLM↔LLM = md / person = HTML)
The PLAN LLM simultaneously calculates the two files of "plan/plan.json" + "plan/plan.md"
The driver is parsing only the "plan/plan.json" This test is valid for that parse.

cutover: the old `parse plan frontmatter` (YAML frontmatter) is a determinant.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from engine.core.planning.loader import (
    Phase,
    Plan,
    PlanLoaderError,
    parse_plan_json,
)


def _write_plan_json(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _good_payload() -> dict:
    return {
        "schema_version": 2,
        "work_request": "WR-504",
        "command": "implement",
        "mode": "multi",
        "phases": [
            {
                "id": "P1",
                "title": "first",
                "deps": [],
                "deliverable": "work/P1/W1.md",
                "spawn_mode": "in_place",
                "workers": 1,
                "acceptance_criteria": ["pytest tests/test x.py pass"],
            },
            {
                "id": "P2",
                "title": "second",
                "deps": ["P1"],
                "deliverable": "work/P2/W1.md",
                "spawn_mode": "in_place",
                "workers": 1,
                "acceptance_criteria": ["foo.py"],
            },
        ],
    }


def test_parse_plan_json_basic(tmp_path: Path) -> None:
    path = _write_plan_json(tmp_path, _good_payload())
    plan = parse_plan_json(path)
    assert isinstance(plan, Plan)
    assert plan.schema_version == 2
    assert plan.work_request == "WR-504"
    assert plan.command == "implement"
    assert plan.mode == "multi"
    assert len(plan.phases) == 2
    assert plan.phases[0].id == "P1"
    assert plan.phases[0].deps == []
    assert plan.phases[1].deps == ["P1"]
    assert plan.phases[1].deliverable == "work/P2/W1.md"
    assert plan.phases[0].workers == 1
    assert plan.phases[0].acceptance_criteria == ["pytest tests/test x.py pass"]


def test_parse_plan_json_dataclass_types(tmp_path: Path) -> None:
    path = _write_plan_json(tmp_path, _good_payload())
    plan = parse_plan_json(path)
    for ph in plan.phases:
        assert isinstance(ph, Phase)
        assert isinstance(ph.deps, list)
        assert isinstance(ph.acceptance_criteria, list)


def test_parse_plan_json_phase_id_duplicate(tmp_path: Path) -> None:
    """PlanLoaderError"""
    payload = _good_payload()
    payload["phases"][1]["id"] = "P1"  # duplicate
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="duplicate"):
        parse_plan_json(path)


def test_parse_plan_json_deps_unknown(tmp_path: Path) -> None:
    """see Phase id that deps does not exist → PlanLoaderError."""
    payload = _good_payload()
    payload["phases"][1]["deps"] = ["P_DOES_NOT_EXIST"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="unknown"):
        parse_plan_json(path)


def test_parse_plan_json_deps_self_reference(tmp_path: Path) -> None:
    """deps sees themselves → PlanLoaderError."""
    payload = _good_payload()
    payload["phases"][0]["deps"] = ["P1"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="self"):
        parse_plan_json(path)


def test_parse_plan_json_acceptance_empty_for_implement(tmp_path: Path) -> None:
    """Copyright © 2020 PlanLoaderError. All rights reserved."""
    payload = _good_payload()
    payload["phases"][0]["acceptance_criteria"] = []
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="acceptance_criteria"):
        parse_plan_json(path)


def test_parse_plan_json_acceptance_empty_for_research_ok(tmp_path: Path) -> None:
    """Accepts acceptance criteria empty list for command=research."""
    payload = _good_payload()
    payload["command"] = "research"
    payload["phases"][0]["acceptance_criteria"] = []
    payload["phases"][1]["acceptance_criteria"] = []
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.command == "research"
    assert plan.phases[0].acceptance_criteria == []


def test_parse_plan_json_schema_version_missing(tmp_path: Path) -> None:
    """schema version missing → PlanLoaderError."""
    payload = _good_payload()
    del payload["schema_version"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="schema_version"):
        parse_plan_json(path)


def test_parse_plan_json_phases_empty(tmp_path: Path) -> None:
    """PlanLoaderError"""
    payload = _good_payload()
    payload["phases"] = []
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="phases"):
        parse_plan_json(path)


def test_parse_plan_json_not_json(tmp_path: Path) -> None:
    """JSON parse failed → PlanLoaderError."""
    path = tmp_path / "plan.json"
    path.write_text("not valid json {", encoding="utf-8")
    with pytest.raises(PlanLoaderError, match="JSON"):
        parse_plan_json(path)


def test_parse_plan_json_file_missing(tmp_path: Path) -> None:
    """File Missing → PlanLoaderError."""
    with pytest.raises(PlanLoaderError, match="not found"):
        parse_plan_json(tmp_path / "missing.json")


def test_parse_plan_json_defaults(tmp_path: Path) -> None:
    """Optional field (workers / spawn mode) Apply default when missing."""
    payload = _good_payload()
    # workers and spawn mode removal
    del payload["phases"][0]["workers"]
    del payload["phases"][0]["spawn_mode"]
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.phases[0].workers == 1
    assert plan.phases[0].spawn_mode == "in_place"


def test_parse_plan_json_circular_deps(tmp_path: Path) -> None:
    """Cycle dependence → PlanLoaderError (topo sort failed detection)."""
    payload = _good_payload()
    payload["phases"][0]["deps"] = ["P2"]
    payload["phases"][1]["deps"] = ["P1"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="circular"):
        parse_plan_json(path)


def test_parse_plan_json_sample_wr504(tmp_path: Path) -> None:
    """JSON equivalent to 6 Phase frontmatter of this WR-504 plan."""
    payload = {
        "schema_version": 2,
        "work_request": "WR-504",
        "command": "implement",
        "mode": "multi",
        "phases": [
            {
                "id": pid,
                "title": "t",
                "deps": deps,
                "deliverable": f"work/{pid}/W1.md",
                "spawn_mode": "in_place",
                "workers": 1,
                "acceptance_criteria": ["x"],
            }
            for pid, deps in (
                ("P1", []),
                ("P3", []),
                ("P2", ["P1"]),
                ("P4", ["P3"]),
                ("P5", ["P1", "P3"]),
                ("P6", ["P1", "P2", "P3", "P4", "P5"]),
            )
        ],
    }
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert {p.id for p in plan.phases} == {"P1", "P2", "P3", "P4", "P5", "P6"}


def test_parse_plan_json_unexpected_phase_field(tmp_path: Path) -> None:
    """<# if ( data.meta.album ) { #>{{ data.meta.album }}<# } #>"""
    payload = _good_payload()
    payload["phases"][0]["unknown_field"] = "ignored"
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.phases[0].id == "P1"


def test_parse_plan_json_default_mode(tmp_path: Path) -> None:
    """default = 'multi' when missing mode."""
    payload = _good_payload()
    del payload["mode"]
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.mode == "multi"


def test_parse_plan_json_explicit_single(tmp_path: Path) -> None:
    """mode=single degree top acceptance."""
    payload = _good_payload()
    payload["mode"] = "single"
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.mode == "single"


def test_parse_plan_json_textwrap_dedent_ok() -> None:
    """python source of multi-line JSON as normal (textwrap dedent use pattern)."""
    # good payload
    # sanity test to validate dict comparison staticity after `json.loads`.
    raw = textwrap.dedent(
        """\
        {
          "schema_version": 2,
          "work_request": "WR-504",
          "command": "implement",
          "mode": "multi",
          "phases": [
            {"id": "P1", "title": "t", "deps": [],
             "deliverable": "work/P1/W1.md", "spawn_mode": "in_place",
             "workers": 1, "acceptance_criteria": ["x"]}
          ]
        }
        """
    )
    parsed = json.loads(raw)
    assert parsed["schema_version"] == 2
    assert parsed["phases"][0]["id"] == "P1"
