"""v2 advisory 14+룰 룰베이스 평가 — driver 결정론 재검증.

SPEC.md §9 (14+룰 캐논, T-503 확장) + §9.1 (verdict 판정) + §7.1 (driver 룰베이스 재검증).
LLM 호출 없음.

14 룰 (7 카테고리, T-503 확장):
  R-EXIST-1  report.md 존재             (hard-fail)
  R-EXIST-2  plan.md 존재 (research SKIP)
  R-EXIST-3  status.json + workflow_step 키
  R-EXIST-4  metrics.jsonl ≥ 1 줄
  R-METRIC-2 step.end DONE outcome==ok  (hard-fail)
  R-METRIC-3 tool.deny 0건
  R-GUARD-1  worktree 모드 (research/review SKIP)
  R-GUARD-2  feature branch 존재
  R-GUARD-3  regression.pattern 0건
  R-PATH-1   report.md → plan.md 토큰 (research SKIP)
  R-FSM-1    workflow_step ∈ {DONE, FAILED}
  R-WT-1     commits ahead ≥ 1 (research/review SKIP, hard-fail)
  R-CODE-1   pytest 통과 (research/review SKIP, hard-fail)  # T-503
  R-CODE-2   ruff clean / counts==0 (research/review SKIP, advisory FAIL)  # T-503
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ._common import PROJECT_ROOT, WorkflowContext
from . import _verify_code


HARD_FAIL_RULES = ("R-EXIST-1", "R-METRIC-2", "R-WT-1", "R-CODE-1")


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


def _r_code_pytest(ctx: WorkflowContext) -> RuleResult:
    """R-CODE-1 (T-503): pytest 통과 hard-fail (implement 한정).

    SPEC.md §9 R-CODE-1.
    입력: `validate/code.json` 의 `tools` 안에 `tool=pytest` 항목.
    통과 조건: `status ∈ {ok, skip}`. `fail` 이면 hard-fail.
    research/review → 호출자가 SKIP 처리 (evaluate_rules 에서 분기).
    code.json 미존재 / pytest 항목 미존재 → SKIP (graceful).
    """
    payload = _verify_code.read_code_json(ctx)
    if not payload:
        return RuleResult(
            "R-CODE-1",
            True,
            detail="validate/code.json missing — SKIP (driver _verify_code 호출 회귀)",
            skip=True,
        )
    if payload.get("command_skip"):
        return RuleResult(
            "R-CODE-1",
            True,
            detail=f"command_skip ({payload.get('skip_reason', '')}) — SKIP",
            skip=True,
        )
    entry = _verify_code.tool_result(payload, "pytest")
    if entry is None:
        return RuleResult(
            "R-CODE-1",
            True,
            detail="pytest entry missing in code.json — SKIP",
            skip=True,
        )
    status = entry.get("status", "skip")
    if status == "skip":
        return RuleResult(
            "R-CODE-1",
            True,
            detail=f"pytest skip ({entry.get('reason', '')})",
            skip=True,
        )
    if status == "ok":
        counts = entry.get("counts", {})
        passed = counts.get("passed", 0)
        return RuleResult("R-CODE-1", True, detail=f"pytest passed={passed}")
    # status == "fail" (또는 알 수 없는 값)
    counts = entry.get("counts", {})
    failed = counts.get("failed", 0) + counts.get("errors", 0)
    head = entry.get("head_diagnostics", [])
    head_str = "; ".join(head[:3]) if head else ""
    return RuleResult(
        "R-CODE-1",
        False,
        detail=f"pytest failed={failed} head=[{head_str}]"[:200],
    )


def _r_code_lint(ctx: WorkflowContext) -> RuleResult:
    """R-CODE-2 (T-503): lint clean advisory FAIL (implement 한정).

    SPEC.md §9 R-CODE-2.
    입력: `validate/code.json` 의 `tools` 안에 `tool=ruff` 항목.
    통과 조건: `status ∈ {ok, skip}` 또는 `counts.diagnostics == 0`.
    위반 시 advisory FAIL (hard-fail 아님).
    """
    payload = _verify_code.read_code_json(ctx)
    if not payload:
        return RuleResult(
            "R-CODE-2",
            True,
            detail="validate/code.json missing — SKIP",
            skip=True,
        )
    if payload.get("command_skip"):
        return RuleResult(
            "R-CODE-2",
            True,
            detail="command_skip — SKIP",
            skip=True,
        )
    entry = _verify_code.tool_result(payload, "ruff")
    if entry is None:
        return RuleResult(
            "R-CODE-2",
            True,
            detail="ruff entry missing in code.json — SKIP",
            skip=True,
        )
    status = entry.get("status", "skip")
    if status == "skip":
        return RuleResult(
            "R-CODE-2",
            True,
            detail=f"ruff skip ({entry.get('reason', '')})",
            skip=True,
        )
    counts = entry.get("counts", {})
    diag_count = counts.get("diagnostics", 0)
    if status == "ok" or diag_count == 0:
        return RuleResult("R-CODE-2", True, detail="ruff clean")
    # status == "fail" + diag_count > 0
    head = entry.get("head_diagnostics", [])
    head_str = "; ".join(head[:2]) if head else ""
    return RuleResult(
        "R-CODE-2",
        False,
        detail=f"ruff diagnostics={diag_count} head=[{head_str}]"[:200],
    )


def _r_wt_commits_ahead(ctx: WorkflowContext) -> RuleResult:
    """R-WT-1 (T-489 Stage 3-D): command 별 분기.

    SPEC.md §9.1.1 — implement 만 hard-fail, research/review 는 SKIP.
    feature_branch 미설정 시도 SKIP (driver init_step 가 command=implement
    에 한해 worktree 생성 + feature_branch 채움).
    """
    if ctx.command in ("research", "review"):
        return RuleResult(
            "R-WT-1",
            True,
            detail=f"{ctx.command} SKIP (worktree-less 허용)",
            skip=True,
        )
    if not ctx.feature_branch:
        return RuleResult(
            "R-WT-1",
            False,
            detail="command=implement 인데 feature_branch 없음 — driver init_step 회귀",
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


def evaluate_rules(ctx: WorkflowContext) -> VerdictReport:
    """SPEC.md §9 14+룰 advisory 평가. driver 룰베이스 결정론.

    T-503 — 12룰 → 14+룰 확장 (R-CODE-1 / R-CODE-2 신설). 함수명 정정
    (evaluate_12_rules → evaluate_rules). 옛 이름은 backward compat alias 로 보존.
    """
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
    # R-GUARD-1: worktree 모드 활성. implement 면 ctx.feature_branch 존재로 판정,
    # research/review 면 SKIP (워크트리-less 허용).
    if ctx.command in ("research", "review"):
        rules.append(
            RuleResult(
                "R-GUARD-1",
                True,
                detail=f"{ctx.command} SKIP (worktree-less 허용)",
                skip=True,
            ),
        )
    else:
        ok_wt = bool(ctx.feature_branch)
        rules.append(
            RuleResult(
                "R-GUARD-1",
                ok_wt,
                detail=(
                    f"worktree active (feature_branch={ctx.feature_branch})"
                    if ok_wt
                    else "implement 인데 worktree 미활성 — driver init_step 회귀"
                ),
            ),
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

    # R-CODE (T-503) — implement 한정. research/review SKIP.
    if ctx.command in ("research", "review"):
        rules.append(
            RuleResult("R-CODE-1", True, detail=f"{ctx.command} SKIP", skip=True),
        )
        rules.append(
            RuleResult("R-CODE-2", True, detail=f"{ctx.command} SKIP", skip=True),
        )
    else:
        rules.append(_r_code_pytest(ctx))
        rules.append(_r_code_lint(ctx))

    return _compute_verdict(rules)


# Backward-compat alias — 옛 함수명 보존. driver done_step 의 호출 경로 유지.
def evaluate_12_rules(ctx: WorkflowContext) -> VerdictReport:
    """T-503 이전 함수명. `evaluate_rules` 로 위임. 옛 호출자 보존."""
    return evaluate_rules(ctx)


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
    """validate-rules.json 산출 — driver 평가 결과 박제.

    T-503 — flat (옛, backward compat) + nested (`validate/rules.json`) 동시 작성.
    """
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
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    path = ctx.validate_rules_json_path()
    path.write_text(serialized, encoding="utf-8")
    nested = ctx.validate_rules_json_nested_path()
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text(serialized, encoding="utf-8")
    return path
