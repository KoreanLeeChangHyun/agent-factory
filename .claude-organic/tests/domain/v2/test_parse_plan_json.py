"""test_parse_plan_json.py — T-504 P1 (TDD Red→Green→Refactor).

대상: `engine.v2.core.plan_loader` 모듈의 `parse_plan_json` (JSON SSOT 파서).

T-504 캐논 SSOT (driver = JSON / LLM↔LLM = md / 사람 = HTML) 에 따라
PLAN LLM 은 `plan/plan.json` + `plan/plan.md` 두 파일을 동시 산출하며,
driver 는 `plan/plan.json` 만 결정론 파싱한다. 본 테스트는 그 파서를 검증.

cutover: 옛 `parse_plan_frontmatter` (YAML frontmatter) 는 통째 폐기.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from engine.v2.core.plan_loader import (
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
        "ticket": "T-504",
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
                "acceptance_criteria": ["pytest tests/test_x.py 통과"],
            },
            {
                "id": "P2",
                "title": "second",
                "deps": ["P1"],
                "deliverable": "work/P2/W1.md",
                "spawn_mode": "in_place",
                "workers": 1,
                "acceptance_criteria": ["foo.py 존재"],
            },
        ],
    }


def test_parse_plan_json_basic(tmp_path: Path) -> None:
    path = _write_plan_json(tmp_path, _good_payload())
    plan = parse_plan_json(path)
    assert isinstance(plan, Plan)
    assert plan.schema_version == 2
    assert plan.ticket == "T-504"
    assert plan.command == "implement"
    assert plan.mode == "multi"
    assert len(plan.phases) == 2
    assert plan.phases[0].id == "P1"
    assert plan.phases[0].deps == []
    assert plan.phases[1].deps == ["P1"]
    assert plan.phases[1].deliverable == "work/P2/W1.md"
    assert plan.phases[0].workers == 1
    assert plan.phases[0].acceptance_criteria == ["pytest tests/test_x.py 통과"]


def test_parse_plan_json_dataclass_types(tmp_path: Path) -> None:
    path = _write_plan_json(tmp_path, _good_payload())
    plan = parse_plan_json(path)
    for ph in plan.phases:
        assert isinstance(ph, Phase)
        assert isinstance(ph.deps, list)
        assert isinstance(ph.acceptance_criteria, list)


def test_parse_plan_json_phase_id_duplicate(tmp_path: Path) -> None:
    """동일 Phase id 두 번 → PlanLoaderError."""
    payload = _good_payload()
    payload["phases"][1]["id"] = "P1"  # duplicate
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="duplicate"):
        parse_plan_json(path)


def test_parse_plan_json_deps_unknown(tmp_path: Path) -> None:
    """deps 가 존재하지 않는 Phase id 를 참조 → PlanLoaderError."""
    payload = _good_payload()
    payload["phases"][1]["deps"] = ["P_DOES_NOT_EXIST"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="unknown"):
        parse_plan_json(path)


def test_parse_plan_json_deps_self_reference(tmp_path: Path) -> None:
    """deps 가 자기 자신을 참조 → PlanLoaderError."""
    payload = _good_payload()
    payload["phases"][0]["deps"] = ["P1"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="self"):
        parse_plan_json(path)


def test_parse_plan_json_acceptance_empty_for_implement(tmp_path: Path) -> None:
    """command=implement 인데 acceptance_criteria 빈 list → PlanLoaderError."""
    payload = _good_payload()
    payload["phases"][0]["acceptance_criteria"] = []
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="acceptance_criteria"):
        parse_plan_json(path)


def test_parse_plan_json_acceptance_empty_for_research_ok(tmp_path: Path) -> None:
    """command=research 인 경우 acceptance_criteria 빈 list 허용."""
    payload = _good_payload()
    payload["command"] = "research"
    payload["phases"][0]["acceptance_criteria"] = []
    payload["phases"][1]["acceptance_criteria"] = []
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.command == "research"
    assert plan.phases[0].acceptance_criteria == []


def test_parse_plan_json_schema_version_missing(tmp_path: Path) -> None:
    """schema_version 누락 → PlanLoaderError."""
    payload = _good_payload()
    del payload["schema_version"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="schema_version"):
        parse_plan_json(path)


def test_parse_plan_json_phases_empty(tmp_path: Path) -> None:
    """phases 빈 list → PlanLoaderError."""
    payload = _good_payload()
    payload["phases"] = []
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="phases"):
        parse_plan_json(path)


def test_parse_plan_json_not_json(tmp_path: Path) -> None:
    """JSON parse 실패 → PlanLoaderError."""
    path = tmp_path / "plan.json"
    path.write_text("not valid json {", encoding="utf-8")
    with pytest.raises(PlanLoaderError, match="JSON"):
        parse_plan_json(path)


def test_parse_plan_json_file_missing(tmp_path: Path) -> None:
    """파일 미존재 → PlanLoaderError."""
    with pytest.raises(PlanLoaderError, match="not found"):
        parse_plan_json(tmp_path / "missing.json")


def test_parse_plan_json_defaults(tmp_path: Path) -> None:
    """optional 필드 (workers / spawn_mode) 누락 시 default 적용."""
    payload = _good_payload()
    # workers 와 spawn_mode 제거
    del payload["phases"][0]["workers"]
    del payload["phases"][0]["spawn_mode"]
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.phases[0].workers == 1
    assert plan.phases[0].spawn_mode == "in_place"


def test_parse_plan_json_circular_deps(tmp_path: Path) -> None:
    """순환 의존 → PlanLoaderError (topo sort 실패 검출)."""
    payload = _good_payload()
    payload["phases"][0]["deps"] = ["P2"]
    payload["phases"][1]["deps"] = ["P1"]
    path = _write_plan_json(tmp_path, payload)
    with pytest.raises(PlanLoaderError, match="circular"):
        parse_plan_json(path)


def test_parse_plan_json_sample_t504(tmp_path: Path) -> None:
    """본 T-504 plan 의 6 Phase frontmatter 와 동등한 JSON 도 정상 파싱."""
    payload = {
        "schema_version": 2,
        "ticket": "T-504",
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
    """Phase 안에 spec 외 필드 — 현재는 silent ignore (forward compat)."""
    payload = _good_payload()
    payload["phases"][0]["unknown_field"] = "ignored"
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.phases[0].id == "P1"


def test_parse_plan_json_default_mode(tmp_path: Path) -> None:
    """mode 누락 시 default = 'multi'."""
    payload = _good_payload()
    del payload["mode"]
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.mode == "multi"


def test_parse_plan_json_explicit_single(tmp_path: Path) -> None:
    """mode=single 도 정상 수용."""
    payload = _good_payload()
    payload["mode"] = "single"
    path = _write_plan_json(tmp_path, payload)
    plan = parse_plan_json(path)
    assert plan.mode == "single"


def test_parse_plan_json_textwrap_dedent_ok() -> None:
    """python source 의 multi-line JSON 도 정상 (textwrap dedent 사용 패턴)."""
    # 본 테스트는 _good_payload 와 다르게, JSON 문자열을 inline 생성하여
    # `json.loads` 후 dict 비교 정합성을 검증하는 sanity test.
    raw = textwrap.dedent(
        """\
        {
          "schema_version": 2,
          "ticket": "T-504",
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
