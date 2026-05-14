"""test_verify.py — _verify.py 단위 테스트.

대상:
  - parse_plan_frontmatter (단순 YAML parser, 4 키 + phases list)
  - topo_sort (정상 / circular / unknown dep)
  - verify_artifact (file exist + size + must_contain)
  - verify_plan_md (frontmatter 검증 + phases + topo)
  - verify_work_md / verify_work_set
  - verify_report_md (plan.md 토큰 매칭)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from engine.v2._verify import (
    Phase,
    parse_plan_frontmatter,
    topo_sort,
    verify_artifact,
    verify_plan_md,
    verify_report_md,
    verify_validate_md,
    verify_work_md,
    verify_work_set,
)


def test_parse_plan_frontmatter_basic() -> None:
    sample = textwrap.dedent(
        """\
        ---
        schema_version: 1
        ticket: T-489
        command: implement
        mode: multi
        phases:
          - id: P1
            title: "core"
            deps: []
            deliverable: work/P1.md
            spawn_mode: in_place
          - id: P2
            title: "next"
            deps: [P1]
            deliverable: work/P2.md
        ---

        # body
        """
    )
    fm = parse_plan_frontmatter(sample)
    assert fm is not None
    assert fm.schema_version == 1
    assert fm.ticket == "T-489"
    assert fm.command == "implement"
    assert fm.mode == "multi"
    assert len(fm.phases) == 2
    assert fm.phases[0].id == "P1"
    assert fm.phases[0].deps == []
    assert fm.phases[1].deps == ["P1"]
    # default spawn_mode
    assert fm.phases[1].spawn_mode == "in_place"


def test_parse_plan_frontmatter_no_frontmatter() -> None:
    assert parse_plan_frontmatter("# just body\n") is None


def test_parse_plan_frontmatter_unclosed() -> None:
    assert parse_plan_frontmatter("---\nticket: T-1\nphases: []\n") is None


def test_topo_sort_normal_chain() -> None:
    phases = [
        Phase(id="C", title="", deps=["A", "B"]),
        Phase(id="A", title="", deps=[]),
        Phase(id="B", title="", deps=["A"]),
    ]
    result = topo_sort(phases)
    assert result is not None
    order = [p.id for p in result]
    assert order.index("A") < order.index("B")
    assert order.index("B") < order.index("C")


def test_topo_sort_circular() -> None:
    phases = [
        Phase(id="A", title="", deps=["B"]),
        Phase(id="B", title="", deps=["A"]),
    ]
    assert topo_sort(phases) is None


def test_topo_sort_unknown_dep() -> None:
    phases = [Phase(id="A", title="", deps=["Z_missing"])]
    assert topo_sort(phases) is None


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


def test_verify_plan_md_full(tmp_path: Path) -> None:
    p = tmp_path / "plan.md"
    p.write_text(
        textwrap.dedent(
            """\
            ---
            schema_version: 1
            ticket: T-1
            command: implement
            mode: multi
            phases:
              - id: P1
                title: "x"
                deps: []
                deliverable: work/P1.md
            ---

            body
            """
        ),
        encoding="utf-8",
    )
    assert verify_plan_md(p).ok


def test_verify_plan_md_no_phases(tmp_path: Path) -> None:
    p = tmp_path / "plan.md"
    p.write_text(
        textwrap.dedent(
            """\
            ---
            schema_version: 1
            ticket: T-1
            phases: []
            ---

            body
            """
        ),
        encoding="utf-8",
    )
    result = verify_plan_md(p)
    assert not result.ok
    assert any("empty" in m or "parse failed" in m for m in result.missing)


def test_verify_work_set_partial(tmp_path: Path) -> None:
    p1 = tmp_path / "P1.md"
    p2 = tmp_path / "P2.md"
    p1.write_text("body 1 with enough chars", encoding="utf-8")
    # p2 missing
    result = verify_work_set([p1, p2])
    assert not result.ok
    assert any("P2.md" in m for m in result.missing)


def test_verify_report_md_token_match(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    plan = tmp_path / "plan.md"
    plan.write_text("dummy", encoding="utf-8")
    report.write_text("## summary\nrefers to plan.md output\n" + "x" * 50, encoding="utf-8")
    assert verify_report_md(report, plan).ok


def test_verify_report_md_token_missing(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    plan = tmp_path / "plan.md"
    plan.write_text("dummy", encoding="utf-8")
    report.write_text("body without the required token " * 5, encoding="utf-8")
    result = verify_report_md(report, plan)
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
