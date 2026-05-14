"""v2 advisory 12룰 룰베이스 평가 — driver 결정론 재검증.

SPEC.md §9 (12룰 캐논) + §9.1 (verdict 판정) + §7.1 (driver 룰베이스 재검증).
LLM 호출 없음.

12 룰 (6 카테고리):
  R-EXIST-1  report.md 존재             (hard-fail)
  R-EXIST-2  plan.md 존재 (research SKIP)
  R-EXIST-3  status.json + workflow_step 키
  R-EXIST-4  metrics.jsonl ≥ 1 줄
  R-METRIC-2 step.end DONE outcome==ok  (hard-fail)
  R-METRIC-3 tool.deny 0건
  R-GUARD-1  worktree 모드 (v2 prototype = SKIP)
  R-GUARD-2  feature branch 존재
  R-GUARD-3  regression.pattern 0건
  R-PATH-1   report.md → plan.md 토큰 (research SKIP)
  R-FSM-1    workflow_step ∈ {DONE, FAILED}
  R-WT-1     commits ahead ≥ 1 (research/review SKIP, hard-fail)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ._common import PROJECT_ROOT, WorkflowContext


HARD_FAIL_RULES = ("R-EXIST-1", "R-METRIC-2", "R-WT-1")


@dataclass
class RuleResult:
    """단일 룰 평가 결과."""

    rule_id: str
    ok: bool
    detail: str = ""
    skip: bool = False


@dataclass
class VerdictReport:
    """SPEC.md §9.1 verdict 판정 결과."""

    verdict: str  # PASS / WARN / FAIL / SKIP
    rules: list[RuleResult] = field(default_factory=list)

    def violation_count(self) -> int:
        return sum(1 for r in self.rules if not r.ok and not r.skip)

    def has_hard_fail(self) -> bool:
        return any(
            (not r.ok) and (not r.skip) and (r.rule_id in HARD_FAIL_RULES)
            for r in self.rules
        )


# -------- 카테고리 평가 함수 --------


def _read_jsonl_events(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _r_exist(path: Path, rule_id: str) -> RuleResult:
    if not path.exists():
        return RuleResult(rule_id, False, detail=f"{path.name} not found")
    if path.stat().st_size <= 0:
        return RuleResult(rule_id, False, detail=f"{path.name} empty")
    return RuleResult(rule_id, True)


def _r_status_workflow_step(ctx: WorkflowContext) -> RuleResult:
    path = ctx.status_json_path()
    if not path.exists():
        return RuleResult("R-EXIST-3", False, detail="status.json not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return RuleResult("R-EXIST-3", False, detail=f"status.json parse: {exc}")
    if not isinstance(data, dict) or "workflow_step" not in data:
        return RuleResult(
            "R-EXIST-3",
            False,
            detail="status.json missing 'workflow_step' key",
        )
    return RuleResult("R-EXIST-3", True)


def _r_metric_done_outcome(ctx: WorkflowContext) -> RuleResult:
    path = ctx.metrics_jsonl_path()
    last_outcome: str | None = None
    for obj in _read_jsonl_events(path):
        if obj.get("event") == "step.end" and obj.get("step") == "DONE":
            last_outcome = obj.get("outcome")
    if last_outcome != "ok":
        return RuleResult(
            "R-METRIC-2",
            False,
            detail=f"step.end DONE outcome={last_outcome!r}",
        )
    return RuleResult("R-METRIC-2", True)


def _r_metric_no_tool_deny(ctx: WorkflowContext) -> RuleResult:
    deny_count = sum(
        1 for obj in _read_jsonl_events(ctx.metrics_jsonl_path())
        if obj.get("event") == "tool.deny"
    )
    if deny_count > 0:
        return RuleResult("R-METRIC-3", False, detail=f"tool.deny count={deny_count}")
    return RuleResult("R-METRIC-3", True)


def _r_feature_branch(ctx: WorkflowContext) -> RuleResult:
    if not ctx.feature_branch:
        return RuleResult(
            "R-GUARD-2",
            True,
            detail="no feature_branch (worktree-less)",
            skip=True,
        )
    result = subprocess.run(
        ["git", "branch", "--list", ctx.feature_branch],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    if not result.stdout.strip():
        return RuleResult(
            "R-GUARD-2",
            False,
            detail=f"branch {ctx.feature_branch!r} not found",
        )
    return RuleResult("R-GUARD-2", True)


def _r_no_regression_pattern(ctx: WorkflowContext) -> RuleResult:
    count = sum(
        1 for obj in _read_jsonl_events(ctx.metrics_jsonl_path())
        if obj.get("event") == "regression.pattern"
    )
    if count > 0:
        return RuleResult("R-GUARD-3", False, detail=f"regression.pattern count={count}")
    return RuleResult("R-GUARD-3", True)


def _r_path_plan_match(ctx: WorkflowContext) -> RuleResult:
    report = ctx.report_md_path()
    if not report.exists():
        return RuleResult(
            "R-PATH-1",
            False,
            detail="report.md not found (cascading from R-EXIST-1)",
        )
    text = report.read_text(encoding="utf-8")
    if "plan.md" not in text:
        return RuleResult("R-PATH-1", False, detail="report.md missing 'plan.md' token")
    return RuleResult("R-PATH-1", True)


def _r_fsm_terminal(ctx: WorkflowContext) -> RuleResult:
    path = ctx.status_json_path()
    if not path.exists():
        return RuleResult("R-FSM-1", False, detail="status.json not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return RuleResult("R-FSM-1", False, detail=f"parse: {exc}")
    step = data.get("workflow_step", "NONE")
    if step not in ("DONE", "FAILED"):
        return RuleResult(
            "R-FSM-1",
            True,
            detail=f"workflow_step={step!r} not terminal",
            skip=True,
        )
    return RuleResult("R-FSM-1", True, detail=f"workflow_step={step}")


def _r_wt_commits_ahead(ctx: WorkflowContext) -> RuleResult:
    """R-WT-1: T-486 Phase 2b 에서 hard-fail 승격.

    v2 prototype 은 worktree 없이 develop 에서 직접 작업 — feature_branch
    설정 시에만 실측 검증, 아니면 SKIP.
    """
    if not ctx.feature_branch:
        return RuleResult(
            "R-WT-1",
            True,
            detail="v2 worktree-less prototype",
            skip=True,
        )
    result = subprocess.run(
        ["git", "rev-list", "--count", f"develop..{ctx.feature_branch}"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    if result.returncode != 0:
        return RuleResult(
            "R-WT-1",
            False,
            detail=f"git rev-list error: {result.stderr.strip()[:100]}",
        )
    count = int(result.stdout.strip() or "0")
    if count < 1:
        return RuleResult("R-WT-1", False, detail="commits ahead == 0")
    return RuleResult("R-WT-1", True, detail=f"commits ahead = {count}")


# -------- 12룰 통합 평가 --------


def evaluate_12_rules(ctx: WorkflowContext) -> VerdictReport:
    """SPEC.md §9 12룰 advisory 평가. driver 룰베이스 결정론."""
    rules: list[RuleResult] = []

    # R-EXIST
    rules.append(_r_exist(ctx.report_md_path(), "R-EXIST-1"))
    if ctx.command == "research":
        rules.append(RuleResult("R-EXIST-2", True, detail="research SKIP", skip=True))
    else:
        rules.append(_r_exist(ctx.plan_md_path(), "R-EXIST-2"))
    rules.append(_r_status_workflow_step(ctx))
    rules.append(_r_exist(ctx.metrics_jsonl_path(), "R-EXIST-4"))

    # R-METRIC
    rules.append(_r_metric_done_outcome(ctx))
    rules.append(_r_metric_no_tool_deny(ctx))

    # R-GUARD
    rules.append(
        RuleResult("R-GUARD-1", True, detail="v2 worktree-less prototype", skip=True),
    )
    rules.append(_r_feature_branch(ctx))
    rules.append(_r_no_regression_pattern(ctx))

    # R-PATH
    if ctx.command == "research":
        rules.append(RuleResult("R-PATH-1", True, detail="research SKIP", skip=True))
    else:
        rules.append(_r_path_plan_match(ctx))

    # R-FSM
    rules.append(_r_fsm_terminal(ctx))

    # R-WT
    if ctx.command in ("research", "review"):
        rules.append(
            RuleResult("R-WT-1", True, detail=f"{ctx.command} SKIP", skip=True),
        )
    else:
        rules.append(_r_wt_commits_ahead(ctx))

    return _compute_verdict(rules)


def _compute_verdict(rules: list[RuleResult]) -> VerdictReport:
    """SPEC.md §9.1 — PASS / WARN / FAIL / SKIP."""
    violations = [r for r in rules if not r.ok and not r.skip]
    has_hard_fail = any(r.rule_id in HARD_FAIL_RULES for r in violations)

    if not violations:
        verdict = "PASS"
    elif has_hard_fail or len(violations) >= 3:
        verdict = "FAIL"
    else:
        verdict = "WARN"
    return VerdictReport(verdict=verdict, rules=rules)


def save_verdict_report(ctx: WorkflowContext, report: VerdictReport) -> Path:
    """validate-rules.json 산출 — driver 평가 결과 박제."""
    payload = {
        "schema_version": 1,
        "verdict": report.verdict,
        "violation_count": report.violation_count(),
        "has_hard_fail": report.has_hard_fail(),
        "hard_fail_rules": list(HARD_FAIL_RULES),
        "rules": [
            {
                "rule_id": r.rule_id,
                "ok": r.ok,
                "skip": r.skip,
                "detail": r.detail,
            }
            for r in report.rules
        ],
    }
    path = ctx.work_dir / "validate-rules.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
