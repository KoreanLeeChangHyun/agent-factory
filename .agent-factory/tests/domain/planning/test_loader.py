"""Tests for core planning loader exports."""

from __future__ import annotations

import json
from pathlib import Path

from engine.core.planning.loader import Phase, parse_plan_json, topo_levels


def test_parse_plan_json_loads_core_plan(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "ticket": "T-504",
                "command": "implement",
                "mode": "multi",
                "phases": [
                    {
                        "id": "P1",
                        "title": "first",
                        "deps": [],
                        "deliverable": "work/P1/W1.md",
                        "acceptance_criteria": ["done"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = parse_plan_json(path)

    assert plan.ticket == "T-504"
    assert plan.phases[0].id == "P1"


def test_topo_levels_groups_parallel_phases() -> None:
    phases = [
        Phase(id="P1", title="", deps=[]),
        Phase(id="P2", title="", deps=[]),
        Phase(id="P3", title="", deps=["P1", "P2"]),
    ]

    levels = topo_levels(phases)

    assert [[phase.id for phase in level] for level in levels] == [
        ["P1", "P2"],
        ["P3"],
    ]

