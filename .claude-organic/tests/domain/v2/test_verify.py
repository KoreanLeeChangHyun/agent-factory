"""test_verify.py — _verify.py 단위 테스트 (T-504 cutover).

T-504 cutover: 옛 `parse_plan_frontmatter` / `_extract_frontmatter` / `verify_plan_md`
대상 테스트는 폐기. 신규 PLAN 산출물 (plan/plan.json + plan/plan.md) 검증은
`verify_plan_artifacts` + `engine.v2.core.plan_loader.parse_plan_json` 으로 분리.

대상:
  - verify_artifact (file exist + size + must_contain)
  - verify_plan_artifacts (T-504 — JSON + MD 양쪽 + 스키마)
  - verify_work_md / verify_work_set
  - verify_report_html (T-504 — 옛 verify_report_md 통째 폐기, plan.md 토큰 매칭)
  - Phase / topo_sort re-export (backward compat)
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.v2._verify import (
    Phase,
    topo_sort,
    verify_artifact,
    verify_plan_artifacts,
    verify_report_html,
    verify_validate_md,
    verify_work_md,
    verify_work_set,
)


def _good_plan_payload() -> dict:
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
                "acceptance_criteria": ["x"],
            }
        ],
    }


def test_verify_artifact_missing(tmp_path: Path) -> None:
    result = verify_artifact(tmp_path / "nope.md")
    assert not result.ok
    assert any("file not found" in m for m in result.missing)


def test_verify_artifact_too_small(tmp_path: Path) -> None:
    p = tmp_path / "tiny.md"
    p.write_text("", encoding="utf-8")
    result = verify_artifact(p, min_size=10)
    assert not result.ok
    assert any("too small" in m for m in result.missing)


def test_verify_artifact_must_contain(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("hello world", encoding="utf-8")
    ok = verify_artifact(p, must_contain=("hello",))
    fail = verify_artifact(p, must_contain=("missing-token",))
    assert ok.ok
    assert not fail.ok
    assert any("missing-token" in m for m in fail.missing)


def test_verify_plan_artifacts_full(tmp_path: Path) -> None:
    """T-504 — plan.json + plan.md 모두 있고 schema 정합 → PASS."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text(
        json.dumps(_good_plan_payload()), encoding="utf-8"
    )
    (plan_dir / "plan.md").write_text(
        "# plan body\n자연어 본문 (20자 이상)\n" + "x" * 30, encoding="utf-8"
    )
    result = verify_plan_artifacts(plan_dir / "plan.json", plan_dir / "plan.md")
    assert result.ok
    assert result.missing == []


def test_verify_plan_artifacts_json_missing(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.md").write_text("body" * 20, encoding="utf-8")
    result = verify_plan_artifacts(plan_dir / "plan.json", plan_dir / "plan.md")
    assert not result.ok
    assert any("plan.json" in m for m in result.missing)


def test_verify_plan_artifacts_md_missing(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text(
        json.dumps(_good_plan_payload()), encoding="utf-8"
    )
    result = verify_plan_artifacts(plan_dir / "plan.json", plan_dir / "plan.md")
    assert not result.ok
    assert any("plan.md" in m for m in result.missing)


def test_verify_plan_artifacts_invalid_schema(tmp_path: Path) -> None:
    """plan.json 스키마 위반 → schema error 추가."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    bad = _good_plan_payload()
    bad["phases"] = []  # 빈 phases
    (plan_dir / "plan.json").write_text(json.dumps(bad), encoding="utf-8")
    (plan_dir / "plan.md").write_text("body" * 20, encoding="utf-8")
    result = verify_plan_artifacts(plan_dir / "plan.json", plan_dir / "plan.md")
    assert not result.ok
    assert any("schema error" in m for m in result.missing)


def test_verify_work_set_partial(tmp_path: Path) -> None:
    p1 = tmp_path / "P1.md"
    p2 = tmp_path / "P2.md"
    p1.write_text("body 1 with enough chars", encoding="utf-8")
    # p2 missing
    result = verify_work_set([p1, p2])
    assert not result.ok
    assert any("P2.md" in m for m in result.missing)


def test_verify_report_html_token_match(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    plan = tmp_path / "plan" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("dummy", encoding="utf-8")
    report.write_text(
        "<html><body>refers to plan.md output</body></html>" + "x" * 50,
        encoding="utf-8",
    )
    assert verify_report_html(report, plan).ok


def test_verify_report_html_token_missing(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    plan = tmp_path / "plan" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("dummy", encoding="utf-8")
    report.write_text("body without the required token " * 5, encoding="utf-8")
    result = verify_report_html(report, plan)
    assert not result.ok
    assert any("plan.md" in m for m in result.missing)


def test_verify_validate_md_minimal(tmp_path: Path) -> None:
    vr = tmp_path / "vr.md"
    vr.write_text("## verdict: PASS\nadvisory body" * 2, encoding="utf-8")
    assert verify_validate_md(vr).ok


def test_verify_work_md_size(tmp_path: Path) -> None:
    p = tmp_path / "P1.md"
    p.write_text("ok body content here exists", encoding="utf-8")
    assert verify_work_md(p).ok


def test_phase_topo_sort_re_export() -> None:
    """T-504 — Phase / topo_sort 는 core.plan_loader SSOT 에서 re-export."""
    phases = [
        Phase(id="C", title="", deps=["A", "B"]),
        Phase(id="A", title="", deps=[]),
        Phase(id="B", title="", deps=["A"]),
    ]
    result = topo_sort(phases)
    assert result is not None
    order = [p.id for p in result]
    assert order.index("A") < order.index("B") < order.index("C")
