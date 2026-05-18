"""test_validate.py — _validate.py 12룰 룰베이스 평가 단위 테스트.

대상:
  - 12 룰 각각 (R-EXIST-1~4 / R-METRIC-2~3 / R-GUARD-1~3 / R-PATH-1 / R-FSM-1 / R-WT-1)
  - verdict 판정: PASS / WARN / FAIL
  - hard-fail rules (R-EXIST-1 / R-METRIC-2 / R-WT-1) 1+ 위반 → FAIL
  - research / review 명령 SKIP 분기
  - validate-rules.json 산출 + schema
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.v2._common import WorkflowContext, write_status
from engine.v2._validate import (
    HARD_FAIL_RULES,
    RuleResult,
    VerdictReport,
    evaluate_12_rules,
    evaluate_rules,
    save_verdict_report,
)


def _make_ctx(tmp_path: Path, command: str = "implement") -> WorkflowContext:
    (tmp_path / "work").mkdir(exist_ok=True)
    ctx = WorkflowContext(
        ticket_no="T-489",
        registry_key="20260515-000000",
        work_dir=tmp_path,
        command=command,
        mode="multi",
        current_step="DONE",
    )
    return ctx


def _setup_passing_artifacts(ctx: WorkflowContext) -> None:
    """모든 룰 PASS 시나리오 — verdict=PASS 기대."""
    # R-EXIST-1: report.md
    ctx.report_md_path().write_text(
        "## summary\n본 사이클은 plan.md 의 결정에 따라 진행.\n" * 3,
        encoding="utf-8",
    )
    # R-EXIST-2: plan.md
    ctx.plan_md_path().write_text("---\nticket: T-1\n---\n\n# body\n", encoding="utf-8")
    # R-EXIST-3: status.json + workflow_step
    write_status(ctx, {"workflow_step": "DONE", "transitions": []})
    # R-EXIST-4 + R-METRIC-2: metrics.jsonl 에 step.end DONE outcome=ok
    ctx.metrics_jsonl_path().write_text(
        '{"event":"step.start","step":"DONE","ts":"2026-05-15T00:00:00"}\n'
        '{"event":"step.end","step":"DONE","outcome":"ok","ts":"2026-05-15T00:00:01"}\n',
        encoding="utf-8",
    )


def test_hard_fail_rules_canon() -> None:
    # T-503 — hard-fail rules 4종 (R-EXIST-1 + R-METRIC-2 + R-WT-1 + R-CODE-1).
    assert HARD_FAIL_RULES == ("R-EXIST-1", "R-METRIC-2", "R-WT-1", "R-CODE-1")


def test_all_pass(tmp_path: Path) -> None:
    # Stage 3-D 정합: command=implement 면 feature_branch 필수.
    # 테스트에서는 worktree 분기 우회 위해 command=research 로 PASS 시나리오 구성.
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    report = evaluate_12_rules(ctx)
    assert report.verdict == "PASS", f"expected PASS, got {report.verdict}: {report.rules}"
    assert report.violation_count() == 0
    assert not report.has_hard_fail()


def test_r_exist_1_report_missing(tmp_path: Path) -> None:
    """R-EXIST-1 hard-fail → verdict=FAIL."""
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    ctx.report_md_path().unlink()
    report = evaluate_12_rules(ctx)
    assert report.has_hard_fail()
    assert report.verdict == "FAIL"


def test_r_exist_2_plan_skipped_for_research(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    ctx.plan_md_path().unlink()  # research 라 SKIP
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-EXIST-2")
    assert rule.skip
    assert report.verdict == "PASS"


def test_r_exist_3_status_missing_key(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    ctx.status_json_path().write_text('{"transitions": []}', encoding="utf-8")
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-EXIST-3")
    assert not rule.ok
    assert "workflow_step" in rule.detail


def test_r_metric_2_done_outcome_fail(tmp_path: Path) -> None:
    """step.end DONE outcome != ok → hard-fail."""
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    ctx.metrics_jsonl_path().write_text(
        '{"event":"step.end","step":"DONE","outcome":"fail"}\n',
        encoding="utf-8",
    )
    report = evaluate_12_rules(ctx)
    assert report.has_hard_fail()
    assert report.verdict == "FAIL"


def test_r_metric_3_tool_deny_violation(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    # tool.deny 1건 → R-METRIC-3 위반 (hard-fail 아님 → WARN)
    with ctx.metrics_jsonl_path().open("a", encoding="utf-8") as fh:
        fh.write('{"event":"tool.deny","tool":"Bash"}\n')
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-METRIC-3")
    assert not rule.ok
    assert report.verdict in ("WARN", "FAIL")


def test_r_guard_3_regression_pattern(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    with ctx.metrics_jsonl_path().open("a", encoding="utf-8") as fh:
        fh.write('{"event":"regression.pattern","pattern":"worker_false_success"}\n')
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-GUARD-3")
    assert not rule.ok
    assert "count=1" in rule.detail


def test_r_path_1_report_missing_token(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    # report.md 에서 plan.md 토큰 제거
    ctx.report_md_path().write_text("body without the token " * 10, encoding="utf-8")
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-PATH-1")
    assert not rule.ok
    assert "plan.md" in rule.detail


def test_r_fsm_1_terminal_pass(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    # workflow_step = DONE 정합
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-FSM-1")
    assert rule.ok


def test_r_fsm_1_non_terminal_skip(tmp_path: Path) -> None:
    """workflow_step 이 WORK 등 비종료 시 → SKIP (advisory)."""
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    write_status(ctx, {"workflow_step": "WORK", "transitions": []})
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-FSM-1")
    assert rule.skip


def test_r_wt_1_research_skip(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-WT-1")
    assert rule.skip


def test_r_wt_1_review_skip(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, command="review")
    _setup_passing_artifacts(ctx)
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-WT-1")
    assert rule.skip


def test_r_guard_1_skip_research(tmp_path: Path) -> None:
    """Stage 3-D 정합: research → R-GUARD-1 SKIP."""
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-GUARD-1")
    assert rule.skip


def test_r_guard_1_implement_no_branch_fail(tmp_path: Path) -> None:
    """Stage 3-D 정합: implement + feature_branch=None → R-GUARD-1 FAIL."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    assert ctx.feature_branch is None
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-GUARD-1")
    assert not rule.ok
    assert "implement" in rule.detail


def test_r_guard_2_no_feature_branch_skip(tmp_path: Path) -> None:
    """ctx.feature_branch=None 시 SKIP (worktree-less)."""
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    assert ctx.feature_branch is None
    report = evaluate_12_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-GUARD-2")
    assert rule.skip


def test_verdict_warn_with_one_violation(tmp_path: Path) -> None:
    """1 위반 + hard-fail 0건 → WARN. Stage 3-D 정합: research 베이스로 PASS 시나리오 구성."""
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    # 1 룰만 깨뜨림 — R-METRIC-3 (tool.deny)
    with ctx.metrics_jsonl_path().open("a", encoding="utf-8") as fh:
        fh.write('{"event":"tool.deny","tool":"Bash"}\n')
    report = evaluate_12_rules(ctx)
    assert report.verdict == "WARN"
    assert report.violation_count() == 1


def test_verdict_fail_with_three_violations(tmp_path: Path) -> None:
    """3+ 위반 → FAIL (hard-fail 없어도)."""
    ctx = _make_ctx(tmp_path)
    _setup_passing_artifacts(ctx)
    with ctx.metrics_jsonl_path().open("a", encoding="utf-8") as fh:
        fh.write('{"event":"tool.deny","tool":"A"}\n')
        fh.write('{"event":"regression.pattern","pattern":"X"}\n')
    # report.md 의 plan.md 토큰도 제거
    ctx.report_md_path().write_text("body without token " * 10, encoding="utf-8")
    report = evaluate_12_rules(ctx)
    assert report.violation_count() >= 3
    assert report.verdict == "FAIL"


def test_save_verdict_report_schema(tmp_path: Path) -> None:
    # Stage 3-D 정합: research 베이스로 PASS schema 검증
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    report = evaluate_12_rules(ctx)
    out_path = save_verdict_report(ctx, report)
    assert out_path == ctx.validate_rules_json_path()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["verdict"] == "PASS"
    assert payload["violation_count"] == 0
    assert payload["has_hard_fail"] is False
    assert payload["hard_fail_rules"] == list(HARD_FAIL_RULES)
    rule_ids = [r["rule_id"] for r in payload["rules"]]
    # T-503 — 14 룰 모두 존재 (R-CODE-1/2 신설).
    expected = [
        "R-EXIST-1", "R-EXIST-2", "R-EXIST-3", "R-EXIST-4",
        "R-METRIC-2", "R-METRIC-3",
        "R-GUARD-1", "R-GUARD-2", "R-GUARD-3",
        "R-PATH-1", "R-FSM-1", "R-WT-1",
        "R-CODE-1", "R-CODE-2",
    ]
    assert rule_ids == expected


def test_save_verdict_report_writes_nested_mirror(tmp_path: Path) -> None:
    """T-503 wire-up — validate/rules.json (nested) 도 동시 작성."""
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    report = evaluate_12_rules(ctx)
    save_verdict_report(ctx, report)
    flat = ctx.validate_rules_json_path()
    nested = ctx.validate_rules_json_nested_path()
    assert flat.exists()
    assert nested.exists()
    assert flat.read_text(encoding="utf-8") == nested.read_text(encoding="utf-8")


def test_verdict_report_helpers() -> None:
    rules = [
        RuleResult("R-EXIST-1", False, "report.md missing"),  # hard-fail
        RuleResult("R-EXIST-2", True),
    ]
    report = VerdictReport(verdict="FAIL", rules=rules)
    assert report.violation_count() == 1
    assert report.has_hard_fail()


# -------- T-503 R-CODE 룰 신설 테스트 --------


def _write_code_json(ctx: WorkflowContext, payload: dict) -> None:
    """validate/code.json fixture writer — P4 `_verify_code.read_code_json` 의 입력."""
    code_path = ctx.validate_code_json_path()
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_r_code_1_skip_no_code_json(tmp_path: Path) -> None:
    """R-CODE-1: validate/code.json 미존재 → SKIP (driver _verify_code 호출 회귀)."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-1")
    assert rule.skip
    assert "missing" in rule.detail.lower()


def test_r_code_1_skip_command_skip(tmp_path: Path) -> None:
    """R-CODE-1: code.json 의 command_skip=True → SKIP."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": True,
            "skip_reason": "test override",
            "tools": [],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-1")
    assert rule.skip
    assert "command_skip" in rule.detail


def test_r_code_1_skip_pytest_missing(tmp_path: Path) -> None:
    """R-CODE-1: code.json 에 pytest 항목 미존재 → SKIP."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [{"tool": "ruff", "status": "ok", "counts": {"diagnostics": 0}}],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-1")
    assert rule.skip


def test_r_code_1_skip_pytest_status_skip(tmp_path: Path) -> None:
    """R-CODE-1: pytest status=skip (도구 미설치 / 설정 부재) → SKIP."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [
                {"tool": "pytest", "status": "skip", "reason": "pytest not installed",
                 "counts": {}, "head_diagnostics": [], "duration_ms": 0},
            ],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-1")
    assert rule.skip
    assert "pytest skip" in rule.detail


def test_r_code_1_pass(tmp_path: Path) -> None:
    """R-CODE-1: pytest status=ok → PASS."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [
                {"tool": "pytest", "status": "ok", "rc": 0,
                 "counts": {"passed": 10}, "head_diagnostics": [], "duration_ms": 100},
            ],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-1")
    assert rule.ok
    assert not rule.skip
    assert "passed=10" in rule.detail


def test_r_code_1_fail_hard_fail(tmp_path: Path) -> None:
    """R-CODE-1: pytest status=fail → hard-fail (verdict FAIL 강제)."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    # implement 시나리오에서 다른 룰을 PASS 시키려면 feature_branch + git 매칭 필요.
    # 본 테스트는 R-CODE-1 hard-fail 만 검증 — has_hard_fail() True.
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [
                {"tool": "pytest", "status": "fail", "rc": 1,
                 "counts": {"failed": 3, "passed": 5},
                 "head_diagnostics": ["FAILED tests/test_x.py::test_y", "FAILED tests/test_z.py::test_w"],
                 "duration_ms": 200},
            ],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-1")
    assert not rule.ok
    assert not rule.skip
    assert "failed=3" in rule.detail
    assert report.has_hard_fail()
    assert report.verdict == "FAIL"


def test_r_code_1_research_skip(tmp_path: Path) -> None:
    """R-CODE-1: command=research → SKIP (worktree-less, 코드 변경 동반 X)."""
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-1")
    assert rule.skip
    assert "research" in rule.detail


def test_r_code_2_skip_no_ruff(tmp_path: Path) -> None:
    """R-CODE-2: code.json 에 ruff 항목 미존재 → SKIP."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [{"tool": "pytest", "status": "skip", "counts": {}, "head_diagnostics": []}],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-2")
    assert rule.skip


def test_r_code_2_pass_ok(tmp_path: Path) -> None:
    """R-CODE-2: ruff status=ok → PASS."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [
                {"tool": "ruff", "status": "ok", "rc": 0,
                 "counts": {"diagnostics": 0}, "head_diagnostics": []},
            ],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-2")
    assert rule.ok
    assert "clean" in rule.detail


def test_r_code_2_pass_zero_diagnostics(tmp_path: Path) -> None:
    """R-CODE-2: ruff status=fail 이지만 counts.diagnostics=0 → PASS (graceful)."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [
                {"tool": "ruff", "status": "fail",
                 "counts": {"diagnostics": 0}, "head_diagnostics": []},
            ],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-2")
    assert rule.ok


def test_r_code_2_advisory_fail_no_hard_fail(tmp_path: Path) -> None:
    """R-CODE-2: ruff diagnostics > 0 → advisory FAIL (hard-fail 아님)."""
    ctx = _make_ctx(tmp_path, command="implement")
    _setup_passing_artifacts(ctx)
    _write_code_json(
        ctx,
        {
            "schema_version": 1,
            "command": "implement",
            "command_skip": False,
            "tools": [
                {"tool": "ruff", "status": "fail", "rc": 1,
                 "counts": {"diagnostics": 5},
                 "head_diagnostics": ["E501 line too long", "F401 unused import"]},
            ],
        },
    )
    report = evaluate_rules(ctx)
    rule = next(r for r in report.rules if r.rule_id == "R-CODE-2")
    assert not rule.ok
    assert not rule.skip
    assert "diagnostics=5" in rule.detail
    # R-CODE-2 는 hard-fail 아님 — 단독 위반은 WARN 또는 FAIL (다른 룰 합산 시)
    assert "R-CODE-2" not in HARD_FAIL_RULES


def test_evaluate_rules_14_rules_total(tmp_path: Path) -> None:
    """T-503 — evaluate_rules 가 14 룰을 모두 반환 (research baseline)."""
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    report = evaluate_rules(ctx)
    assert len(report.rules) == 14
    rule_ids = [r.rule_id for r in report.rules]
    assert "R-CODE-1" in rule_ids
    assert "R-CODE-2" in rule_ids


def test_evaluate_12_rules_alias_returns_same(tmp_path: Path) -> None:
    """T-503 — 옛 evaluate_12_rules alias 가 evaluate_rules 와 동일 결과 (backward compat)."""
    ctx = _make_ctx(tmp_path, command="research")
    _setup_passing_artifacts(ctx)
    new_report = evaluate_rules(ctx)
    old_report = evaluate_12_rules(ctx)
    assert old_report.verdict == new_report.verdict
    assert len(old_report.rules) == len(new_report.rules)
    new_ids = [r.rule_id for r in new_report.rules]
    old_ids = [r.rule_id for r in old_report.rules]
    assert old_ids == new_ids
